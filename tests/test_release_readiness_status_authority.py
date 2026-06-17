from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "docs" / "initiatives" / "contextforge-control-plane" / "release-readiness-report.md"
CHECKLIST = REPO_ROOT / "docs" / "initiatives" / "contextforge-control-plane" / "acceptance-checklist.md"
RUNBOOK = REPO_ROOT / "docs" / "initiatives" / "contextforge-control-plane" / "implementation-runbook.md"
SKILL_REF = REPO_ROOT / ".codex" / "skills" / "contextforge-control-plane" / "references" / "evidence-and-tests.md"


class ReleaseReadinessStatusAuthorityTests(unittest.TestCase):
    def test_release_readiness_report_is_current_d17_d18_authority(self) -> None:
        report = REPORT.read_text(encoding="utf-8")

        self.assertIn("D0-D17 are complete after Wave 12 QA and root adjudication", report)
        self.assertIn("D18 is pending W13-QA and root adjudication", report)
        self.assertIn("W13-QA remains pending", report)

    def test_active_guidance_no_longer_claims_d17_pending(self) -> None:
        forbidden = "D17 remains pending"

        for path in [CHECKLIST, SKILL_REF]:
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                self.assertNotIn(forbidden, path.read_text(encoding="utf-8"))

    def test_checklist_is_classified_as_historical_wave_12_evidence(self) -> None:
        checklist = CHECKLIST.read_text(encoding="utf-8")
        normalized = " ".join(checklist.split())

        self.assertIn("historical Wave 12 gate evidence", checklist)
        self.assertIn("current authority is", checklist)
        self.assertIn("release-readiness-report.md", checklist)
        self.assertIn("D17 is complete", normalized)
        self.assertIn("D18 remains pending W13-QA/root adjudication", normalized)

    def test_runbook_remaining_gates_are_classified_as_historical_context(self) -> None:
        runbook = RUNBOOK.read_text(encoding="utf-8")
        normalized = " ".join(runbook.split())

        self.assertIn("historical Wave 12-C gate context", normalized)
        self.assertIn("release-readiness-report.md", normalized)
        self.assertIn("D17 complete after Wave 12 QA/root adjudication", normalized)
        self.assertIn("D18 pending W13-QA/root adjudication", normalized)

    def test_skill_reference_points_to_release_readiness_report(self) -> None:
        skill_ref = SKILL_REF.read_text(encoding="utf-8")

        self.assertIn("release-readiness-report.md", skill_ref)
        self.assertIn("D0-D17 are complete", skill_ref)
        self.assertIn("D18 remains pending W13-QA and root adjudication", skill_ref)


if __name__ == "__main__":
    unittest.main()
