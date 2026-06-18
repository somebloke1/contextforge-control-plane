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

    def test_index_maps_current_open_issues_and_recent_prs(self) -> None:
        for reference in [
            "Open issues after this refresh",
            "#52: guided MCP service-onboarding helper",
            "#3: host Pi global ContextForge shim prompt/resource parity",
            "#2: deferred Serena runtime blockers",
            "#87 merged the #52 source/docs/tests fixture increment",
            "#88 merged the source/docs/tests path-index refresh",
            "#90 merged the client-visible activation matrix",
            "#92 merged the #91 path-index topology refresh",
            "#93 merged the #52 source-only resume envelope",
            "#94 merged the #52 opt-in local ignored session store",
            "#98 merged the #97 safe client-visible validation probe catalog",
            "#100 merged the #99 Context7 safe-probe policy contract",
            "#102 merged the #101 Context7 safe-probe validation result builder",
            "#104 merged the #103 helper guidance",
            "#106 merged the #105 Mentality safe-probe policy contract",
            "#110 merged the #109 ssh-tmux safe-probe policy contract",
            "#114 merged the #113 OpenZeppelin Solidity Contracts safe-probe policy",
            "#116 merged the #115 path-index refresh",
            "#117 merged the #52 service-onboarding session-status readback",
            "#119 merged the #118 path-index refresh",
            "#121 merged the #120 first real OpenZeppelin service-onboarding fixture",
            "#123 merged the #122 path-index refresh",
            "#125 merged the #124 service-onboarding session-list readback",
            "closed #89",
            "Recently closed path-setting issues include #124",
        ]:
            self.assertIn(reference, self.index)
        self.assertNotIn("#126: post-merge refresh for this development path index", self.index)
        self.assertNotIn("#122: post-merge refresh for this development path index", self.index)
        self.assertNotIn("#118: post-merge refresh for this development path index", self.index)
        self.assertNotIn("#115: post-merge refresh for this development path index", self.index)
        self.assertNotIn("#111: post-merge refresh for this development path index", self.index)
        self.assertNotIn("#107: post-merge refresh for this development path index", self.index)
        self.assertNotIn("#95: post-merge refresh for this development path index", self.index)
        self.assertNotIn("#91: post-merge refresh for this development path index", self.index)

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
            "#97/#98 added the first source/docs/tests safe-probe catalog",
            "#99/#100 added the Context7 safe-probe policy contract",
            "#101/#102 added the Context7 safe-probe validation result builder",
            "#103/#104 updated helper guidance",
            "#105/#106 added the Mentality safe-probe policy contract",
            "#109/#110 added the ssh-tmux safe-probe policy contract",
            "#113/#114 added the OpenZeppelin Solidity Contracts safe-probe policy",
            "They do not prove live",
            "generated Solidity is audited or deployable",
            "conditional-probe scoping for remaining credential, browser",
            "GitHub, web-search, Exa Search, Playwright",
            "operator productization",
            "next dev Docker service expansion",
            "late legacy-retirement phase",
        ]:
            self.assertIn(candidate, self.index)

        self.assertIn("promoted to #89/#90", self.index)
        self.assertIn("Safe client-visible validation probes` was promoted through", self.index)
        self.assertIn("#97/#99/#101/#103/#105/#109/#113", self.index)
        self.assertIn("Do not implement these gaps from this index alone.", self.index)

    def test_index_records_service_onboarding_status_readback(self) -> None:
        for text in [
            "#69 merged the first deterministic no-mutation onboarding-record helper",
            "#87 merged a source/docs/tests increment",
            "#93 merged a source-only resume envelope",
            "#94 merged opt-in project-local ignored session persistence",
            "#117 merged compact read-only status summaries",
            "`--session-status <session-id>`",
            "known/open classifications",
            "answered/next questions",
            "#121 merged the first real tracked service-onboarding fixture",
            "`openzeppelin_remote_native_hosted_source_only`",
            "generated Solidity audit/deployability",
            "#125 merged compact read-only inventory",
            "`--list-sessions`",
            "`service_onboarding_session_list`",
            "absent-store empty-list behavior",
            "saved-record-name ordering",
            "rejection of descriptor, resume, status, or\n  write options",
            "richer local\n  dialogue/session management",
            "status readback, and\n  list readback",
            "another selected service record",
        ]:
            self.assertIn(text, self.index)

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
            "Workflow Knowledge Persistence",
            "Persist the workflow automation map in this skill",
            "read Project #6",
            "workflow contract",
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
