from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_readiness_claim_linter as linter


FIXTURE = REPO_ROOT / "tests" / "fixtures" / "control_plane_readiness_claim_cases.json"
GUARDRAILS = REPO_ROOT / "docs" / "readiness-claim-guardrails.md"
SURFACE_LABELS = REPO_ROOT / "docs" / "evidence-surface-labels.md"
FRESHNESS_PROTOCOL = REPO_ROOT / "docs" / "dev-docker-client-evidence-freshness-protocol.md"


def cases_by_name() -> dict[str, dict[str, object]]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {case["name"]: case for case in data["cases"]}


class ControlPlaneReadinessClaimLinterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = cases_by_name()

    def assert_codes(self, case_name: str) -> None:
        case = self.cases[case_name]
        diagnostics = linter.lint_text(str(case["text"]), source=case_name)
        self.assertEqual(list(case["expected_codes"]), [item["code"] for item in diagnostics])
        for diagnostic in diagnostics:
            self.assertEqual(case_name, diagnostic["source"])
            self.assertGreaterEqual(diagnostic["line"], 1)
            self.assertLessEqual(len(diagnostic["excerpt"]), 220)
            self.assertEqual("warning", diagnostic["severity"])

    def test_fixture_cases_emit_expected_diagnostics(self) -> None:
        for case_name in self.cases:
            with self.subTest(case=case_name):
                self.assert_codes(case_name)

    def test_report_has_stable_schema_and_file_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sample = Path(tmpdir) / "overclaim.md"
            sample.write_text(str(self.cases["backend_only_claimed_as_target_client_ready"]["text"]), encoding="utf-8")
            report = linter.lint_files([sample])

        self.assertEqual(1, report["schema_version"])
        self.assertEqual("contextforge://control-plane/schemas/readiness-claim-lint/v1", report["schema_uri"])
        self.assertEqual("failed", report["status"])
        self.assertEqual(1, len(report["files"]))
        self.assertEqual(str(sample), report["files"][0]["path"])
        self.assertEqual(report["diagnostic_count"], report["files"][0]["diagnostic_count"])
        self.assertGreater(report["diagnostic_count"], 0)

    def test_selected_docs_do_not_trigger_readiness_overclaim_warnings(self) -> None:
        for path in [GUARDRAILS, SURFACE_LABELS, FRESHNESS_PROTOCOL]:
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                self.assertEqual([], linter.lint_text(path.read_text(encoding="utf-8"), source=str(path)))

    def test_cli_reports_json_and_nonzero_on_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sample = Path(tmpdir) / "overclaim.md"
            sample.write_text(str(self.cases["backend_only_claimed_as_target_client_ready"]["text"]), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "control_plane_readiness_claim_linter.py"), str(sample)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        report = json.loads(result.stdout)
        self.assertEqual("failed", report["status"])
        self.assertGreater(report["diagnostic_count"], 0)
        self.assertEqual("", result.stderr)

    def test_cli_reports_zero_when_stdin_has_no_diagnostics(self) -> None:
        case = self.cases["source_ready_with_current_evidence_surface_and_boundary"]
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "control_plane_readiness_claim_linter.py")],
            input=str(case["text"]),
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        report = json.loads(result.stdout)
        self.assertEqual("passed", report["status"])
        self.assertEqual([], report["diagnostics"])


if __name__ == "__main__":
    unittest.main()
