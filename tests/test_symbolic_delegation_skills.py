import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / ".codex" / "skills"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class SymbolicSkillSetTests(unittest.TestCase):
    def test_shared_scheme_defines_cross_skill_topology_and_boundaries(self):
        shared = read("SHARED_SYMBOL_SCHEME.md")

        for token in [
            "RC",
            "SO",
            "DM",
            "DG",
            "WK",
            "GP",
            "DC",
            "Sp",
            "M55",
            "M54m",
            "RC → SO → DM → DG → WK → SO",
            "DM ⊥ SO",
            "DC ⊥ L",
            "E ⊥ ✓",
            "GP ⊥ issue/PR/doc",
            "Sp ⊥ judgment",
        ]:
            self.assertIn(token, shared)

    def test_dispatch_matrix_owns_model_policy_without_controller_authority(self):
        skill = read("contextforge-agent-dispatch-matrix/SKILL.md")
        ref = read("contextforge-agent-dispatch-matrix/references/dispatch-card.md")

        for token in ["PE", "SE", "CO", "FC", "MC", "DM ⊥ SO", "selected_model"]:
            self.assertIn(token, skill)
        for token in ["Spark", "gpt-5.3-codex-spark", "gpt-5.5", "gpt-5.4-mini"]:
            self.assertIn(token, ref)
        self.assertIn("fork_context=true", ref)
        self.assertIn("fork_context=false", ref)
        self.assertIn("acceptance_owner", ref)

    def test_delegator_preserves_spawn_gate_contract_and_goal_loop(self):
        skill = read("sub-agent-delegator/SKILL.md")

        for token in [
            "SG(T)",
            "CT",
            "IL",
            "GL",
            "AP",
            "DG ⟡ SO",
            "WK output = E; WK output ∉ ✓",
            "W=/home/dgk/workspace/cf-controlplane",
            "lossless chaining",
        ]:
            self.assertIn(token, skill)

        for forbidden in [
            "registry mutation",
            "branch pushes",
            "PR creation",
            "ledger mutation",
        ]:
            self.assertIn(forbidden, skill)

    def test_superloop_preserves_controller_runtime_protocols(self):
        skill = read("superloop-agent-orchestration/SKILL.md")

        for token in [
            "CID",
            "CR",
            "SL",
            "WP",
            "CD",
            "GR",
            "QL",
            "BD",
            "AD",
            "codex-thread:<thread-id>",
            "codex-agent:<agent-id>",
            "get_goal().goal.threadId",
            "dev-root",
            "codex/issue-<number>-<short-slug>",
            "Agent owner",
            "Agent state",
            "initial_worker_formal_goal",
        ]:
            self.assertIn(token, skill)

        self.assertIn("WK/child output = E, not ✓", skill)
        self.assertIn("SO accepts WK output only if", skill)

    def test_worker_preserves_lease_identity_authority_and_reporting(self):
        skill = read("superloop-worker-agent/SKILL.md")

        for token in [
            "WF",
            "WI",
            "DC✓",
            "WA",
            "LC",
            "WR",
            "ST",
            "lease_id_unavailable",
            "codex-agent:<lease-or-dispatcher-id>",
            "Agent owner",
            "Agent state",
            "selected_model",
            "acceptance_owner",
        ]:
            self.assertIn(token, skill)

        self.assertIn("L ∉ substitute for active explicit user approval", skill)
        self.assertIn("selected M unsuitable for T", skill)

    def test_spark_is_positioned_as_accelerant_not_judgment_owner(self):
        joined = "\n".join(
            read(path)
            for path in [
                "SHARED_SYMBOL_SCHEME.md",
                "contextforge-agent-dispatch-matrix/SKILL.md",
                "contextforge-agent-dispatch-matrix/references/dispatch-card.md",
                "superloop-worker-agent/SKILL.md",
            ]
        )

        for allowed in [
            "mechanical",
            "evidence",
            "scaffold",
            "bounded",
        ]:
            self.assertIn(allowed, joined)
        for forbidden in [
            "architecture",
            "approval",
            "registry",
            "security",
            "governance",
        ]:
            self.assertIn(forbidden, joined)


if __name__ == "__main__":
    unittest.main()
