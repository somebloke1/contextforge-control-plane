from __future__ import annotations

import importlib.util
import sys
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "superloop_reentry_card.py"

spec = importlib.util.spec_from_file_location("superloop_reentry_card", SCRIPT)
assert spec is not None
superloop_reentry_card = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = superloop_reentry_card
spec.loader.exec_module(superloop_reentry_card)


class FakeGitRunner:
    def __init__(self, outputs: dict[tuple[str, ...], str]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args, cwd, **kwargs):  # type: ignore[override]
        key = tuple(args)
        self.calls.append(key)
        if key not in self.outputs:
            raise AssertionError(f"unhandled git command: {key}")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=self.outputs[key], stderr="")


class SuperLoopReentryCardTests(unittest.TestCase):
    def test_card_falls_back_to_placeholders_and_blocks_unsafe_resume(self) -> None:
        runner = FakeGitRunner(
            {
                ("git", "rev-parse", "--abbrev-ref", "HEAD"): "feature/reentry\n",
                ("git", "status", "--short", "--branch"): "## feature/reentry...origin/dev-root [ahead 3]\nM  file.txt\n",
                ("git", "merge-base", "origin/dev-root", "feature/reentry"): "feedbeef\n",
                ("git", "rev-list", "--count", "origin/dev-root..feature/reentry"): "3\n",
                ("git", "rev-list", "--count", "feature/reentry..origin/dev-root"): "0\n",
            }
        )

        card = superloop_reentry_card.build_reentry_card(
            repo_root=REPO_ROOT,
            runner=runner,
            issue=None,
            pr=None,
            project_item=None,
            base="origin/dev-root",
        )

        self.assertEqual("placeholder", card["active_scope"]["issue"]["id"])
        self.assertEqual("placeholder", card["active_scope"]["pull_request"]["id"])
        self.assertEqual("placeholder", card["active_scope"]["project_item"]["id"])
        self.assertIn("legacy/live ContextForge mutation", card["prohibited_surfaces"])
        self.assertIn("hook trust/state", card["prohibited_surfaces"])
        self.assertIn("helper apply/recovery state", card["prohibited_surfaces"])
        self.assertEqual("Re-run with explicit issue/PR/project scope inputs before any state-changing action. This resume card is intentionally conservative until scope is explicit.",
                         card["next_safe_action"])
        self.assertFalse(card["branch_state"]["clean"])

    def test_card_respects_explicit_scope_and_markers(self) -> None:
        runner = FakeGitRunner(
            {
                ("git", "rev-parse", "--abbrev-ref", "HEAD"): "feature/reentry\n",
                ("git", "status", "--short", "--branch"): "## feature/reentry...origin/dev-root\n",
                ("git", "merge-base", "origin/dev-root", "feature/reentry"): "abc123\n",
                ("git", "rev-list", "--count", "origin/dev-root..feature/reentry"): "1\n",
                ("git", "rev-list", "--count", "feature/reentry..origin/dev-root"): "0\n",
            }
        )

        card = superloop_reentry_card.build_reentry_card(
            repo_root=REPO_ROOT,
            runner=runner,
            issue="#191",
            issue_state="open",
            issue_title="Add compact SuperLoop re-entry card",
            pr="#88",
            pr_state="merged",
            project_item="#6",
            project_state="in_progress",
            base="origin/dev-root",
            controller_run_id="codex-thread:test-thread",
            worker_agent_id="codex-agent:test-worker",
        )

        self.assertEqual("191", card["active_scope"]["issue"]["id"])
        self.assertEqual("88", card["active_scope"]["pull_request"]["id"])
        self.assertEqual("#6", card["active_scope"]["project_item"]["id"])
        self.assertIn("local git", card["evidence_authority"][0]["source"])
        self.assertIn("Proceed read-only:", card["next_safe_action"])
        self.assertEqual("codex-thread:test-thread", card["reentry_identity"]["controller_run_id"])
        self.assertEqual("codex-agent:test-worker", card["reentry_identity"]["worker_agent_id"])
        self.assertEqual("abc123", card["branch_state"]["merge_base"])
        self.assertEqual(1, card["branch_state"]["ahead"])
        self.assertEqual(0, card["branch_state"]["behind"])


if __name__ == "__main__":
    unittest.main()
