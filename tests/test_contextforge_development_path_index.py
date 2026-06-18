from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/contextforge-development-path-index.md"
ROADMAP = ROOT / "docs/project-status-roadmap-2026-06-16.md"


class ContextForgeDevelopmentPathIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = INDEX.read_text(encoding="utf-8")
        cls.roadmap = ROADMAP.read_text(encoding="utf-8")

    def test_index_names_required_development_paths(self) -> None:
        for heading in [
            "### Runtime/Service Ops",
            "### Project-State And Helper Control Plane",
            "### Client Adapter And Visible UX",
            "### Dev Docker Integration Lab",
            "### MCP Service Onboarding Lifecycle",
            "### Serena/Project-Scoped Service Lifecycle",
            "### Safe Client-Visible Validation Probes",
            "### Operator Productization",
            "### Governance/Evidence/SuperLoop",
            "### Legacy Retirement",
        ]:
            self.assertIn(heading, self.index)

    def test_index_maps_current_open_issues_and_pr(self) -> None:
        for reference in [
            "#52: guided MCP service-onboarding helper",
            "#3: host Pi global ContextForge shim prompt/resource parity",
            "#2: deferred Serena runtime blockers",
            "#87: draft #52 source/docs/tests fixture increment",
        ]:
            self.assertIn(reference, self.index)

    def test_index_preserves_surface_boundaries(self) -> None:
        for surface in [
            "`legacy/live ContextForge read-only`",
            "`ContextForge dev Docker`",
            "`Pi client Docker`",
            "`OpenCode client Docker`",
        ]:
            self.assertIn(surface, self.index)

        self.assertIn("Do not use legacy/live readback as proof", self.index)
        self.assertIn("Do not use Docker evidence as approval", self.index)

    def test_index_records_gap_issue_candidates_without_implementation(self) -> None:
        for candidate in [
            "client-visible activation UX matrix",
            "safe client-visible validation probes",
            "operator productization",
            "next dev Docker service expansion",
            "late legacy-retirement phase",
        ]:
            self.assertIn(candidate, self.index)

        self.assertIn("Do not implement these gaps from this index alone.", self.index)

    def test_roadmap_links_current_path_index(self) -> None:
        self.assertIn("docs/contextforge-development-path-index.md", self.roadmap)
        self.assertIn("Current development path index", self.roadmap)


if __name__ == "__main__":
    unittest.main()
