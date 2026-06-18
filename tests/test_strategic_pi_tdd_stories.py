from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tests" / "fixtures" / "strategic_pi_tdd_stories.json"
DOC = ROOT / "docs" / "strategic-pi-tdd-stories.md"


class StrategicPiTddStoryCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.stories = cls.catalog["stories"]
        cls.by_issue = {story["issue"]: story for story in cls.stories}
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.normalized_doc = " ".join(cls.doc.split())

    def test_catalog_records_exact_story_set(self) -> None:
        self.assertEqual(26, len(self.stories))
        self.assertEqual(set(range(201, 217)) | set(range(219, 229)), set(self.by_issue))
        self.assertNotIn(217, self.by_issue)
        self.assertNotIn(218, self.by_issue)

    def test_catalog_keeps_intended_and_recovery_counts_distinct(self) -> None:
        counts = Counter(story["story_type"] for story in self.stories)
        self.assertEqual(16, counts["intended_behavior"])
        self.assertEqual(10, counts["failure_recovery"])
        self.assertEqual({"intended_behavior", "failure_recovery"}, set(counts))

    def test_catalog_declares_shared_acceptance_contract(self) -> None:
        self.assertEqual("user_observed_interactive_pi_session", self.catalog["acceptance_gate"])
        self.assertEqual("planned", self.catalog["readiness_floor"])
        self.assertEqual(
            ["user_perception", "technology_narration"],
            self.catalog["required_narration_layers"],
        )
        self.assertEqual(
            ["feature-request", "ideal-form", "validation-request"],
            self.catalog["required_labels"],
        )

    def test_every_story_has_user_and_technical_contracts(self) -> None:
        for story in self.stories:
            with self.subTest(issue=story["issue"]):
                self.assertIsInstance(story["title"], str)
                self.assertIsInstance(story["lane"], str)
                self.assertIn(story["effort"], {"Medium", "High"})
                self.assertIn(story["complexity"], {"Medium", "High"})
                self.assertGreaterEqual(len(story["observable_contract"].split()), 8)
                self.assertGreaterEqual(len(story["technical_contract"].split()), 8)

    def test_failure_recovery_stories_are_structurally_different(self) -> None:
        expected_titles = {
            219: "Dev gateway unreachable at session start",
            220: "Corrupt project-state file blocks activation safely",
            221: "ContextForge server id drift rebind",
            222: "Scoped token expires during interaction",
            223: "Unsafe tool request redirected to safe path",
            224: "Wrapper crash produces bounded diagnostics",
            225: "Project root changes mid-session",
            226: "Concurrent session stale plan conflict",
            227: "Interrupted apply resumes through recovery journal",
            228: "User asks for absent tool and Pi admits gap",
        }

        for issue, title in expected_titles.items():
            with self.subTest(issue=issue):
                self.assertEqual("failure_recovery", self.by_issue[issue]["story_type"])
                self.assertEqual(title, self.by_issue[issue]["title"])

        recovery_lanes = {self.by_issue[issue]["lane"] for issue in expected_titles}
        self.assertGreaterEqual(len(recovery_lanes), 7)

    def test_document_preserves_gate_and_boundaries(self) -> None:
        for phrase in [
            "Issue: #199",
            "#201-#216 are intended-behavior stories",
            "#219-#228 are structurally different failure/recovery stories",
            "Accidental extras #217 and #218 were closed as not planned",
            "must not be closed from source tests",
            "ordinary interactive Pi session",
            "docs/readiness-claim-guardrails.md",
            "not `backend_ready`, `contextforge_ready`, `target_client_ready`, or `verified`",
            "does not approve runtime or Docker work",
            "retired predecessor checkout",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized_doc)

    def test_document_names_each_recovery_story(self) -> None:
        for issue in range(219, 229):
            with self.subTest(issue=issue):
                self.assertIn(f"#{issue}", self.doc)


if __name__ == "__main__":
    unittest.main()
