from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/contextforge-development-path-index.md"
ROADMAP = ROOT / "docs/project-status-roadmap-2026-06-16.md"
PROJECT_SKILL = ROOT / ".codex/skills/github-project-agent-coordination/SKILL.md"


class ContextForgeDevelopmentPathIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = INDEX.read_text(encoding="utf-8")
        cls.roadmap = ROADMAP.read_text(encoding="utf-8")
        cls.project_skill = PROJECT_SKILL.read_text(encoding="utf-8")

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
            "#87 merged the #52 source/docs/tests fixture increment",
        ]:
            self.assertIn(reference, self.index)

        self.assertIn("#88 is the current source/docs/tests path-index refresh vehicle", self.index)

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

    def test_agent_issue_view_protocol_is_recorded(self) -> None:
        for text in [
            "GitHub Project #6",
            "`Agent Issue View`",
            "`Agent state`",
            "coordination index",
            "roadmap draft items",
            "GitHub Project workflows",
            "successor",
            "goals",
        ]:
            self.assertIn(text, self.index)
            self.assertIn(text, self.roadmap)

    def test_project_six_records_roadmap_lane_items(self) -> None:
        for text in [
            "Project #6 Roadmap Draft Items",
            "`Roadmap: Client-visible activation UX matrix`",
            "`Roadmap: Safe client-visible validation probes`",
            "`Roadmap: Operator productization`",
            "`Roadmap: Dev Docker service expansion`",
            "`Roadmap: Project inspector and language-profile proof path`",
            "`Roadmap: Requirement/scenario QA and evidence ledger`",
            "`Roadmap: Upstream ContextForge dependency and packaging watch`",
            "`Roadmap: Security/auth/remote exposure gate`",
            "Keep #2 as the explicit deferred late-phase legacy/Serena blocker",
        ]:
            self.assertIn(text, self.index)

    def test_project_coordination_skill_defines_minimal_board_practice(self) -> None:
        for text in [
            "name: github-project-agent-coordination",
            "Use GitHub Project #6",
            "Read Project #6 `Agent Issue View` during SuperLoop re-entry",
            "Roadmap Draft Items",
            "Configured Project Workflows",
            "`Auto-add to project`: for repository `contextforge-control-plane`, filter",
            "`is:issue,pr is:open`",
            "`Pull request linked to issue`",
            "`Code changes requested`",
            "`Code review approved`",
            "`Pull request merged`",
            "`Auto-close issue`",
            "`Auto-archive items`: filter `is:issue is:closed updated:<@today-2w`",
            "`Status` is workflow-owned",
            "Promote a draft roadmap item to an issue or PR",
            "Add, update, retire, or promote roadmap draft items",
            "Respect configured GitHub Project workflows",
            "workflow-managed status",
            "`Agent state`: agent-facing coordination state",
            "Candidate",
            "Ready",
            "Active",
            "Blocked",
            "In Review",
            "Done",
            "Deferred",
            "gh project item-list 6 --owner somebloke1",
        ]:
            self.assertIn(text, self.project_skill)


if __name__ == "__main__":
    unittest.main()
