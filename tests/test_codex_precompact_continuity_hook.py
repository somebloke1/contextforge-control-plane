from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / ".codex/hooks/contextforge_precompact_continuity.py"

spec = importlib.util.spec_from_file_location("contextforge_precompact_continuity", HOOK_PATH)
assert spec is not None
continuity_hook = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(continuity_hook)


class CodexPrecompactContinuityHookTests(unittest.TestCase):
    def test_precompact_hook_writes_project_local_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            payload = {"hook_event_name": "PreCompact", "trigger": "manual", "thread_id": "thread-1"}

            output = continuity_hook.run(payload, cwd=root, now="2026-06-16T12:00:00-0500")

            self.assertIsNotNone(output)
            assert output is not None
            self.assertNotIn("hookSpecificOutput", output)
            context = output["systemMessage"]
            self.assertIn("run/codex-precompact-continuity/latest.md", context)
            self.assertIn("default compaction prompt authoritative", context)

            state_dir = root / "run/codex-precompact-continuity"
            latest_json = state_dir / "latest.json"
            latest_md = state_dir / "latest.md"
            self.assertTrue(latest_json.exists())
            self.assertTrue(latest_md.exists())

            snapshot = json.loads(latest_json.read_text(encoding="utf-8"))
            self.assertEqual("contextforge-precompact-continuity/v1", snapshot["schema"])
            self.assertEqual("ContextForge", snapshot["project_name"])
            self.assertEqual("manual", snapshot["compaction_trigger"])
            self.assertIn("docs/project-status-roadmap-2026-06-16.md", snapshot["roadmap_refs"])

            markdown = latest_md.read_text(encoding="utf-8")
            self.assertIn("ContextForge Pre-Compaction Continuity Snapshot", markdown)
            self.assertIn("Codex's default compaction prompt remains authoritative", markdown)

    def test_precompact_hook_is_idempotent_for_same_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            payload = {"hook_event_name": "PreCompact", "trigger": "auto", "thread_id": "thread-1"}

            continuity_hook.run(payload, cwd=root, now="2026-06-16T12:00:00-0500")
            continuity_hook.run(payload, cwd=root, now="2026-06-16T12:00:01-0500")

            events = sorted((root / "run/codex-precompact-continuity/events").glob("*.json"))
            self.assertEqual(1, len(events))
            latest = json.loads((root / "run/codex-precompact-continuity/latest.json").read_text(encoding="utf-8"))
            event = json.loads(events[0].read_text(encoding="utf-8"))
            self.assertEqual(event["event_id"], latest["event_id"])

    def test_non_precompact_event_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))

            output = continuity_hook.run({"hook_event_name": "SessionStart"}, cwd=root)

            self.assertIsNone(output)
            self.assertFalse((root / "run/codex-precompact-continuity").exists())

    def test_session_start_compact_returns_documented_additional_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            continuity_hook.run({"hook_event_name": "PreCompact", "trigger": "manual"}, cwd=root)

            output = continuity_hook.run({"hook_event_name": "SessionStart", "source": "compact"}, cwd=root)

            self.assertIsNotNone(output)
            assert output is not None
            hook_output = output["hookSpecificOutput"]
            self.assertEqual("SessionStart", hook_output["hookEventName"])
            self.assertIn("run/codex-precompact-continuity/latest.md", hook_output["additionalContext"])
            self.assertIn("without unchosen loss", hook_output["additionalContext"])

    def test_session_start_compact_without_snapshot_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))

            output = continuity_hook.run({"hook_event_name": "SessionStart", "source": "compact"}, cwd=root)

            self.assertIsNone(output)

    def test_payload_values_are_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            payload = {
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "OPENAI_API_KEY": "sk-secret-value",
                "thread_id": "thread-1",
            }

            continuity_hook.run(payload, cwd=root)

            snapshot_text = (root / "run/codex-precompact-continuity/latest.json").read_text(encoding="utf-8")
            self.assertNotIn("sk-secret-value", snapshot_text)
            self.assertIn("OPENAI_API_KEY:redacted", snapshot_text)

    def test_run_identifier_values_are_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            payload = {
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "hook_run_id": "secret-hook-run-id",
                "hookRunId": "secret-camel-run-id",
                "run_id": "secret-run-id",
                "runId": "secret-run-id-2",
            }

            continuity_hook.run(payload, cwd=root)

            state_dir = root / "run/codex-precompact-continuity"
            snapshot_text = (state_dir / "latest.json").read_text(encoding="utf-8")
            event_names = "\n".join(path.name for path in (state_dir / "events").glob("*.json"))
            self.assertNotIn("secret-hook-run-id", snapshot_text)
            self.assertNotIn("secret-camel-run-id", snapshot_text)
            self.assertNotIn("secret-run-id", snapshot_text)
            self.assertNotIn("secret-hook-run-id", event_names)
            self.assertNotIn("secret-camel-run-id", event_names)
            self.assertNotIn("secret-run-id", event_names)

    def test_main_returns_zero_on_persistence_failure(self) -> None:
        payload = json.dumps({"hook_event_name": "PreCompact", "trigger": "manual"})
        with mock.patch.object(sys, "stdin", io.StringIO(payload)), mock.patch.object(
            continuity_hook,
            "persist_snapshot",
            side_effect=RuntimeError("disk full"),
        ):
            self.assertEqual(0, continuity_hook.main())

    def test_project_config_uses_precompact_without_prompt_overrides(self) -> None:
        config = (REPO_ROOT / ".codex/config.toml").read_text(encoding="utf-8")
        self.assertIn("[[hooks.PreCompact]]", config)
        self.assertIn('matcher = "manual|auto"', config)
        self.assertIn("[[hooks.SessionStart]]", config)
        self.assertIn('matcher = "compact"', config)
        self.assertIn("contextforge_precompact_continuity.py", config)
        self.assertNotIn("compact_prompt", config)
        self.assertNotIn("experimental_compact_prompt_file", config)
        self.assertNotIn("model_auto_compact_token_limit", config)

    def _init_repo(self, root: Path) -> Path:
        (root / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
        (root / "README.md").write_text("# ContextForge\n", encoding="utf-8")
        roadmap = root / "docs/project-status-roadmap-2026-06-16.md"
        roadmap.parent.mkdir(parents=True)
        roadmap.write_text("# ContextForge Roadmap\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "init"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        return root.resolve()


if __name__ == "__main__":
    unittest.main()
