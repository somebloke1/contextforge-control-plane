from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".codex/skills"
SHARED = SKILLS / "SHARED_SYMBOL_SCHEME.md"
DISPATCH = SKILLS / "contextforge-agent-dispatch-matrix/SKILL.md"
CONTROLLER = SKILLS / "superloop-agent-orchestration/SKILL.md"
WORKER = SKILLS / "superloop-worker-agent/SKILL.md"
PROJECT = SKILLS / "github-project-agent-coordination/SKILL.md"


class SuperLoopAgentOrchestrationSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shared = SHARED.read_text(encoding="utf-8")
        cls.dispatch = DISPATCH.read_text(encoding="utf-8")
        cls.controller = CONTROLLER.read_text(encoding="utf-8")
        cls.worker = WORKER.read_text(encoding="utf-8")
        cls.project = PROJECT.read_text(encoding="utf-8")

    def test_shared_scheme_keeps_authority_boundaries_explicit(self) -> None:
        for text in [
            "RC → SO → DM → DG → WK → SO",
            "DM ⊥ SO",
            "DC ⊥ L",
            "E ⊥ ✓",
            "GP ⊥ issue/PR/doc",
            "Sp ⊥ judgment",
            "approval/global/destructive/runtime/shared-system ⇒ SO-only",
        ]:
            self.assertIn(text, self.shared)

    def test_dispatch_matrix_is_advisory_not_controller_replacement(self) -> None:
        for text in [
            "name: contextforge-agent-dispatch-matrix",
            "DM owns {MC, DC schema, SE, CO, FC}",
            "DM ⊥ SO",
            "selected_model",
            "fork_context=true",
            "fork_context=false",
            "Sp ✗",
        ]:
            self.assertIn(text, self.dispatch)

    def test_controller_skill_records_primary_authority(self) -> None:
        for text in [
            "name: superloop-agent-orchestration",
            "This skill is the controller runtime",
            "owns SuperLoop",
            "owns model policy",
            "owns spawn contracts",
            "executes\nleases",
            "owns Project #6 field semantics",
            "CR:",
            "final claims",
            "approval-gated/runtime/destructive/global/shared-system actions",
            "WK/child output = E, not ✓",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_stable_agent_identity(self) -> None:
        for text in [
            "CID",
            "codex-thread:<thread-id>",
            "codex-agent:<agent-id>",
            "codex-agent:<parent-agent-id>/<child-agent-id>",
            "get_goal().goal.threadId",
            "dispatcher/subagent handle",
            "human-readable names = aliases only",
            "agent_run_id",
            "controller_run_id",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_project_lease_model(self) -> None:
        for text in [
            "QL:",
            "WK ✗ pull arbitrary GH issues",
            "default = SO-instantiated, SO-assigned, one bounded T per L",
            "WK-requested work = request, not queue ownership",
            "WK begins only after SO grants/authorizes L",
            "GP.Agent owner",
            "controller-held = codex-thread:<thread-id>",
            "worker-held = codex-agent:<worker-agent-id>",
            "Assignees ∉ agent lease owner",
            "L :=",
            "initial_worker_formal_goal",
            "stop_condition",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_worktree_policy(self) -> None:
        for text in [
            "maintain clean SO baseline on current dev-root",
            "linked worktrees = leased execution surfaces",
            "controller branches start from clean dev-root",
            "unrelated dirty worktree",
            "SO records worktree owner for each active branch/L",
            "returns to clean baseline before final integration",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_tight_branch_develop_merge_cycle(self) -> None:
        for text in [
            "tight branch -> develop -> merge cycle",
            "freshly fetched\n   current `origin/dev-root`",
            "do not stack unrelated work on stale or already\n   merged branches",
            "small enough that the controller can review the diff",
            "Push and open or update the PR as soon as the slice has local evidence",
            "A draft PR is not a storage shelf",
            "refresh `dev-root`, reconcile dependent branches/PRs",
            "closed-unmerged and conflict-bearing branches as debt",
            "record the retirement path and keep them out of the active queue",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_symbolic_branch_discipline(self) -> None:
        for text in [
            "BD:",
            "maintain clean SO baseline on current dev-root",
            "linked worktrees = leased execution surfaces",
            "controller branches start from clean dev-root",
            "worker branch = codex/issue-<number>-<short-slug>",
            "SO records worktree owner for each active branch/L",
            "SO returns to clean baseline before final integration",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_requires_worker_goal_text(self) -> None:
        for text in [
            "initial_worker_formal_goal",
            "formal WK goal",
            "worker G = lease-scoped",
        ]:
            self.assertTrue(text in self.controller or text in self.worker, text)

    def test_controller_skill_defines_worker_pool_cadence(self) -> None:
        for text in [
            "WP:",
            "max_concurrency=3 as cap, not quota",
            "keep verification slot when possible",
            "dispatch only after controller admin is caught up enough to integrate outputs",
            "DG(DC) → L with formal WK goal",
            "set Agent owner only when GP item visible",
            "clean WK+verifier E + expected GH/GP state",
            "WK commit allowed ⇔ L permits ∧ isolated branch/worktree",
            "SO verifies before push/PR/promote/merge/close",
            "no duplicate GP item",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_creative_discussion_agents(self) -> None:
        for text in [
            "CD:",
            "creative GitHub discussion contribution",
            "light prompt; no full L",
            "allowed write = named discussion only",
            "repo read-only",
            "output = idea fuel ∉ roadmap acceptance",
            "SO reads discussion URL → retire agent",
        ]:
            self.assertIn(text, self.controller)

    def test_controller_skill_defines_goal_refinement_and_acceptance(self) -> None:
        for text in [
            "GR:",
            "keep G current at controller boundaries",
            "after completed work batch",
            "after L assignment/WK report/PR merge/issue closure/GP topology change",
            "early pattern → smaller subgoals",
            "✗ complete(G) merely to rewrite",
            "AD:",
            "SO accepts WK output only if",
            "changed files ⊆ allowed set",
            "final claims ≤ exercised surfaces",
            "missing/overbroad E → reject ∨ rescope",
        ]:
            self.assertIn(text, self.controller)

    def test_worker_skill_enforces_assigned_scope_and_boundaries(self) -> None:
        for text in [
            "name: superloop-worker-agent",
            "`WK` owns one `L`",
            "`SO` owns sequencing",
            "worker G ≠ controller G",
            "worker G = lease-scoped",
            "WK ✗ {expand scope, claim global completion, close SO goal, bypass SO}",
            "one assigned issue/validation/audit/implementation/evidence T",
            "PR create/push/merge/promote",
            "governance ledger mutation",
            "L ∉ substitute for active explicit user approval",
        ]:
            self.assertIn(text, self.worker)

    def test_worker_skill_requires_exact_lease_identity_reporting(self) -> None:
        for text in [
            "WI:",
            "worker = codex-agent:<agent-id>",
            "controller = codex-thread:<thread-id>",
            "agent_run_id",
            "controller_run_id",
            "report exact worker ID from L/dispatcher",
            "rotating nickname",
            "lease_id_unavailable",
            "✗ unknown without observed identifier",
        ]:
            self.assertIn(text, self.worker)

    def test_worker_report_template_preserves_evidence_and_non_actions(self) -> None:
        for text in [
            "WR :=",
            "agent_run_id: codex-agent:<lease-or-dispatcher-id>",
            "controller_run_id",
            "assigned_scope",
            "changed files",
            "evidence",
            "non-actions",
            "residual risk",
            "requested controller action",
        ]:
            self.assertIn(text, self.worker)

    def test_worker_stop_conditions_cover_model_and_authority_mismatch(self) -> None:
        for text in [
            "DC✓:",
            "selected_model unsuitable for encountered T → stop(report mismatch)",
            "Sp ✗ {architecture",
            "LC before work:",
            "L ⊥ current GP/repo state → stop(report mismatch)",
            "ST if:",
            "selected M unsuitable for T",
            "approval-gated/runtime/destructive/global/shared-system action required",
            "local success would need global ✓",
        ]:
            self.assertIn(text, self.worker)

    def test_project_skill_documents_agent_owner_field(self) -> None:
        for text in [
            "`Agent owner`: text lease owner",
            "codex-thread:<thread-id>",
            "codex-agent:<worker-agent-id>",
            "codex-agent:<parent-agent-id>/<child-agent-id>",
            "Do not use rotating Codex",
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

    def test_project_skill_defines_branch_and_pr_disposition(self) -> None:
        for text in [
            "Branch And PR Disposition",
            "draft PRs, closed-unmerged PRs, or stale remote branches",
            "branch -> develop -> merge",
            "fresh `origin/dev-root`, small branch, local evidence, PR",
            "A draft PR must have an explicit next action",
            "A conflict-bearing branch is not `Ready`",
            "A closed-unmerged PR is retired unless a controller explicitly reopens",
            "After a merge, reconcile dependent PR bases",
            "If GraphQL budget prevents Project field mutation",
            "do not skip the disposition decision",
        ]:
            self.assertIn(text, self.project)


if __name__ == "__main__":
    unittest.main()
