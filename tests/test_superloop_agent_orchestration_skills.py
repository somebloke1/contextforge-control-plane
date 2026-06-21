from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / ".codex/skills/superloop-agent-orchestration/SKILL.md"
WORKER = ROOT / ".codex/skills/superloop-worker-agent/SKILL.md"
PROJECT = ROOT / ".codex/skills/github-project-agent-coordination/SKILL.md"


class SuperLoopAgentOrchestrationSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.controller = CONTROLLER.read_text(encoding="utf-8")
        cls.worker = WORKER.read_text(encoding="utf-8")
        cls.project = PROJECT.read_text(encoding="utf-8")

    def test_controller_skill_records_primary_authority(self) -> None:
        for text in [
            "name: superloop-agent-orchestration",
            "primary ContextForge SuperLoop controller",
            "global sequencing",
            "worker assignment",
            "Project #6 coordination",
            "GitHub mutations",
            "final acceptance claims",
            "goal maintenance",
            "superloop-worker-agent",
            "sub-agent-delegator",
            "github-project-agent-coordination",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_stable_agent_identity(self) -> None:
        for text in [
            "Use stable run IDs",
            "rotating Codex display names",
            "codex-thread:<thread-id>",
            "codex-agent:<agent-id>",
            "codex-agent:<parent-agent-id>/<child-agent-id>",
            "get_goal().goal.threadId",
            "dispatcher or\nsubagent handle",
            "Human-readable names are aliases only",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_project_lease_model(self) -> None:
        for text in [
            "Workers must not pull arbitrary GitHub issues directly",
            "Project #6 `Agent owner` text field",
            "controller-held item",
            "worker-held item",
            "Do not use `Assignees` as the agent lease owner",
            "The default pattern is\ncontroller-instantiated, controller-assigned work",
            "one bounded work unit",
            "A standing worker may ask for another work unit",
            "must not self-select from the queue",
            "worker-requested work as a request for controller assignment",
            "Work unit lease:",
            "controller_run_id",
            "worker_agent_id",
            "allowed delegation",
            "allowed files/systems/tools",
            "forbidden actions",
            "stop_condition",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_worktree_policy(self) -> None:
        for text in [
            "one clean controller baseline on current\n`dev-root`",
            "separate linked\nworktrees for worker branches",
            "Do not casually move the controller through many dirty worktrees",
            "linked\nworktrees as leased execution surfaces",
            "records which worktree owns each active branch or lease",
            "returns to the clean baseline before final integration",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_requires_worker_goal_text(self) -> None:
        for text in [
            "initial worker formal goal text",
            "worker formal goals remain\nsubordinate",
            "worker successor goal",
            "controller response authorizes",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_goal_refinement_cadence(self) -> None:
        for text in [
            "Goal Refinement Cadence",
            "Keep the formal goal current at controller boundaries",
            "tasklist, issue comments, Project #6 fields, PR notes, or governance ledgers",
            "after each completed work unit or small integrated batch",
            "after any lease assignment, worker report, PR merge, issue closure, or\n  Project topology change",
            "prefer smaller subgoals",
            "do not mark a formal goal complete merely to rewrite it",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_worker_pool_cadence(self) -> None:
        for text in [
            "Worker Pool Cadence",
            "three as a maximum concurrency cap",
            "not a quota to keep full",
            "when the controller would otherwise be idle",
            "integrating returned reports",
            "Keep one slot available for\nverification",
            "do not duplicate worker-local\n   implementation or verification",
            "only if controller administration is caught up",
            "gpt-5.3-codex-spark",
            "Trust the pipeline when evidence is clean",
            "Worker-local commits are acceptable when the lease permits them",
            "Treat the commit as a reviewable artifact",
            "before\npushing, opening PRs, promoting drafts, merging, or closing issues",
            "Do not allow\nworkers to commit on controller baselines",
            "GitHub Project automation has latency",
            "do not\nimmediately create a duplicate Project item",
            "Set `Agent owner` only after the auto-added item is visible",
            "record the pending reconciliation",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_creative_discussion_agents(self) -> None:
        for text in [
            "Creative Discussion Agents",
            "keep the prompt light",
            "Do not wrap idea generation in a full\nwork-unit lease",
            "Send the agent to the discussion",
            "repo/codebase files remain read-only",
            "the named GitHub discussion is writable",
            "idea fuel, not accepted roadmap",
            "read back the discussion URL",
            "whether any idea deserves a real issue,\nProject item, work-unit lease, or governance record",
        ]:
            self.assertIn(text, self.controller)

    def test_worker_skill_enforces_assigned_scope_and_boundaries(self) -> None:
        for text in [
            "name: superloop-worker-agent",
            "operating under a ContextForge controller\nlease",
            "one assigned work unit",
            "Workers may not own unless explicitly leased",
            "final project completion claims",
            "GitHub issue closure",
            "PR creation, push, merge, or draft promotion",
            "Project #6 `Agent owner` matches your worker ID",
            "If the lease and Project state disagree",
            "Stop and hand off",
        ]:
            self.assertIn(text, self.worker)

    def test_worker_skill_requires_lease_scoped_formal_goal(self) -> None:
        for text in [
            "The worker must also operate on a formal SuperLoop goal",
            "lease-scoped goal",
            "Read the worker formal goal",
            "Confirm the goal and lease match",
            "Mark the worker formal goal complete",
            "Create a refined worker successor goal only when",
            "must not use its formal goal to expand scope",
        ]:
            self.assertIn(text, self.worker)

    def test_worker_skill_requires_exact_lease_identity_reporting(self) -> None:
        for text in [
            "Report the worker ID exactly as assigned",
            "Do not substitute a rotating nickname",
            "another agent's ID",
            "lease_id_unavailable",
            "do not write `unknown` without the observed identifier",
            "agent_run_id: codex-agent:<lease-or-dispatcher-id> | lease_id_unavailable",
        ]:
            self.assertIn(text, self.worker)

    def test_worker_report_template_preserves_evidence_and_non_actions(self) -> None:
        for text in [
            "Worker report:",
            "agent_run_id:",
            "controller_run_id:",
            "assigned_scope:",
            "changed files:",
            "evidence:",
            "non-actions:",
            "residual risk:",
            "requested controller action:",
        ]:
            self.assertIn(text, self.worker)

    def test_project_skill_documents_agent_owner_field(self) -> None:
        for text in [
            "`Agent owner`: text lease owner",
            "codex-thread:<thread-id>",
            "codex-agent:<worker-agent-id>",
            "codex-agent:<parent-agent-id>/<child-agent-id>",
            "Do not use rotating Codex",
            "Do not encode semantic pass/fail or readiness",
            "regexes, keyword searches, or string parsing",
            "not an oracle for generated prose",
        ]:
            self.assertIn(text, self.project)

    def test_project_skill_documents_custom_agent_field_automation_boundary(self) -> None:
        for text in [
            "built-in GitHub Project workflows do not\n  clear custom text fields",
            "Custom Agent Field Automation",
            "Treat `Status` as workflow-owned",
            "`Agent state` / `Agent owner` as\nagent-owned",
            "GitHub Actions workflow or a local\ncontroller/helper reconciliation job",
            "clear `Agent owner` when a lease is completed",
            "do not create duplicate Project items while waiting for auto-add latency",
            "Do not infer that `Agent owner` was cleared merely because `Status` is `Done`",
        ]:
            self.assertIn(text, self.project)


if __name__ == "__main__":
    unittest.main()
