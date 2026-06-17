from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_CONTRACT_ROOT = Path(
    os.environ.get("CONTEXTFORGE_CONFIG_CONTRACT_ROOT", "/home/dgk/workspace/cf-controlplane")
)
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
            session_latest_json = self._session_latest_json(root, payload)
            session_latest_md = session_latest_json.with_suffix(".md")
            self.assertIn(str(session_latest_md.relative_to(root)), context)
            self.assertIn("default compaction prompt", context)
            self.assertIn("active goal authoritative", context)

            state_dir = root / "run/codex-precompact-continuity"
            self.assertFalse((state_dir / "latest.json").exists())
            self.assertFalse((state_dir / "latest.md").exists())
            self.assertTrue(session_latest_json.exists())
            self.assertTrue(session_latest_md.exists())

            snapshot = json.loads(session_latest_json.read_text(encoding="utf-8"))
            self.assertEqual("contextforge-precompact-continuity/v1", snapshot["schema"])
            self.assertEqual("ContextForge", snapshot["project_name"])
            self.assertEqual("manual", snapshot["compaction_trigger"])
            self.assertEqual("session", snapshot["authority_scope"])
            self.assertEqual(continuity_hook.session_key(payload, root), snapshot["session_key"])
            self.assertIn("docs/project-status-roadmap-2026-06-16.md", snapshot["roadmap_refs"])
            self.assertIn("promotion_boundary", snapshot)
            self.assertIn("raw_snapshot_policy", snapshot["promotion_boundary"])
            self.assertIn("transition_policy", snapshot["promotion_boundary"])

            markdown = session_latest_md.read_text(encoding="utf-8")
            self.assertIn("ContextForge Pre-Compaction Continuity Snapshot", markdown)
            self.assertIn("Promotion Boundary", markdown)
            self.assertIn("point-in-time evidence", markdown)
            self.assertIn("Codex's default compaction prompt remains authoritative", markdown)

    def test_snapshot_points_to_standard_repo_assets_and_schema(self) -> None:
        snapshot = continuity_hook.build_snapshot(
            {"hook_event_name": "PreCompact", "trigger": "manual", "thread_id": "thread-1"},
            cwd=REPO_ROOT,
            now="2026-06-16T12:00:00-0500",
        )

        self.assertEqual("schemas/codex-precompact-continuity.schema.json", snapshot["schema_ref"])
        standard_refs = snapshot["standard_repo_refs"]
        self.assertIn(".codex/hooks/contextforge_precompact_continuity.py", standard_refs)
        self.assertIn("docs/codex-precompact-continuity-hook.md", standard_refs)
        self.assertIn("schemas/codex-precompact-continuity.schema.json", standard_refs)
        self.assertIn("tests/test_codex_precompact_continuity_hook.py", standard_refs)
        self.assertIn("target operating architecture", snapshot["promotion_boundary"]["transition_policy"])
        self.assertIn(
            "Call get_goal, reconcile the formal goal with the live user mission",
            "\n".join(snapshot["continuity_protocol"]),
        )

        markdown = continuity_hook.render_markdown(snapshot)
        self.assertIn("## Standard Repo Assets", markdown)
        self.assertIn("schemas/codex-precompact-continuity.schema.json", markdown)

    def test_snapshot_schema_file_declares_standard_repo_contract(self) -> None:
        schema = json.loads((REPO_ROOT / "schemas/codex-precompact-continuity.schema.json").read_text(encoding="utf-8"))

        self.assertIn("standard_repo_refs", schema["required"])
        self.assertIn("promotion_boundary", schema["required"])
        self.assertIn("transition_policy", schema["properties"]["promotion_boundary"]["required"])
        self.assertEqual("ContextForge", schema["properties"]["project_name"]["const"])
        self.assertEqual(
            "contextforge-precompact-continuity/v1",
            schema["properties"]["schema"]["const"],
        )

    def test_generated_continuity_state_remains_ignored_runtime_evidence(self) -> None:
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "run/codex-precompact-continuity/sessions/example/latest.json",
                "run/codex-precompact-continuity/events/example.json",
                "run/codex-precompact-continuity/contextforge-precompact-continuity.local.lock",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("run/codex-precompact-continuity/sessions/example/latest.json", result.stdout)
        self.assertIn("run/codex-precompact-continuity/events/example.json", result.stdout)
        self.assertIn("run/codex-precompact-continuity/contextforge-precompact-continuity.local.lock", result.stdout)

    def test_precompact_hook_is_idempotent_for_same_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            payload = {"hook_event_name": "PreCompact", "trigger": "auto", "thread_id": "thread-1"}

            continuity_hook.run(payload, cwd=root, now="2026-06-16T12:00:00-0500")
            continuity_hook.run(payload, cwd=root, now="2026-06-16T12:00:01-0500")

            events = sorted((root / "run/codex-precompact-continuity/events").glob("*.json"))
            self.assertEqual(1, len(events))
            latest = json.loads(self._session_latest_json(root, payload).read_text(encoding="utf-8"))
            event = json.loads(events[0].read_text(encoding="utf-8"))
            self.assertEqual(event["event_id"], latest["event_id"])

    def test_precompact_removes_legacy_global_latest_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            state_dir = root / "run/codex-precompact-continuity"
            state_dir.mkdir(parents=True)
            (state_dir / "latest.json").write_text("{}\n", encoding="utf-8")
            (state_dir / "latest.md").write_text("# stale\n", encoding="utf-8")

            continuity_hook.run(
                {"hook_event_name": "PreCompact", "trigger": "manual", "thread_id": "thread-1"},
                cwd=root,
            )

            self.assertFalse((state_dir / "latest.json").exists())
            self.assertFalse((state_dir / "latest.md").exists())

    def test_non_precompact_event_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))

            output = continuity_hook.run({"hook_event_name": "SessionStart"}, cwd=root)

            self.assertIsNone(output)
            self.assertFalse((root / "run/codex-precompact-continuity").exists())

    def test_session_start_compact_returns_documented_additional_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            payload = {"hook_event_name": "PreCompact", "trigger": "manual", "thread_id": "thread-1"}
            continuity_hook.run(payload, cwd=root)

            output = continuity_hook.run(
                {"hook_event_name": "SessionStart", "source": "compact", "thread_id": "thread-1"},
                cwd=root,
            )

            self.assertIsNotNone(output)
            assert output is not None
            hook_output = output["hookSpecificOutput"]
            self.assertEqual("SessionStart", hook_output["hookEventName"])
            latest_md = str(self._session_latest_json(root, payload).with_suffix(".md").relative_to(root))
            self.assertIn(latest_md, hook_output["additionalContext"])
            self.assertIn("session-scoped additive continuity evidence", hook_output["additionalContext"])
            self.assertIn("active goal authoritative", hook_output["additionalContext"])

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

            snapshot_text = self._session_latest_json(root, payload).read_text(encoding="utf-8")
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
            snapshot_text = "\n".join(
                path.read_text(encoding="utf-8") for path in (state_dir / "events").glob("*.json")
            )
            event_names = "\n".join(path.name for path in (state_dir / "events").glob("*.json"))
            self.assertNotIn("secret-hook-run-id", snapshot_text)
            self.assertNotIn("secret-camel-run-id", snapshot_text)
            self.assertNotIn("secret-run-id", snapshot_text)
            self.assertNotIn("secret-hook-run-id", event_names)
            self.assertNotIn("secret-camel-run-id", event_names)
            self.assertNotIn("secret-run-id", event_names)

    def test_ad_hoc_sessions_do_not_replace_each_other_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            payload_a = {"hook_event_name": "PreCompact", "trigger": "manual", "thread_id": "thread-a"}
            payload_b = {"hook_event_name": "PreCompact", "trigger": "manual", "thread_id": "thread-b"}

            continuity_hook.run(payload_a, cwd=root, now="2026-06-16T12:00:00-0500")
            continuity_hook.run(payload_b, cwd=root, now="2026-06-16T12:00:01-0500")
            output = continuity_hook.run(
                {"hook_event_name": "SessionStart", "source": "compact", "thread_id": "thread-a"},
                cwd=root,
            )

            self.assertIsNotNone(output)
            assert output is not None
            context = output["hookSpecificOutput"]["additionalContext"]
            key_a = continuity_hook.session_key(payload_a, root)
            key_b = continuity_hook.session_key(payload_b, root)
            self.assertIsNotNone(key_a)
            self.assertIsNotNone(key_b)
            assert key_a is not None
            assert key_b is not None
            self.assertIn(f"sessions/{key_a}/latest.md", context)
            self.assertNotIn(f"sessions/{key_b}/latest.md", context)

    def test_precompact_without_session_id_is_event_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._init_repo(Path(tmp))
            payload = {"hook_event_name": "PreCompact", "trigger": "manual"}

            with mock.patch.dict(continuity_hook.os.environ, {}, clear=True):
                output = continuity_hook.run(payload, cwd=root)

                self.assertIsNotNone(output)
                assert output is not None
                self.assertIn("event-only pre-compaction snapshot", output["systemMessage"])
                state_dir = root / "run/codex-precompact-continuity"
                events = sorted((state_dir / "events").glob("*.json"))
                self.assertEqual(1, len(events))
                self.assertFalse((state_dir / "sessions").exists())
                session_start = continuity_hook.run({"hook_event_name": "SessionStart", "source": "compact"}, cwd=root)
                self.assertIsNone(session_start)

    def test_event_snapshot_retention_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(continuity_hook, "MAX_EVENT_SNAPSHOTS", 3):
            root = self._init_repo(Path(tmp))
            last_payload = {}
            for index in range(5):
                last_payload = {
                    "hook_event_name": "PreCompact",
                    "trigger": "manual",
                    "thread_id": "thread-1",
                    "turn_id": f"turn-{index}",
                }
                continuity_hook.run(last_payload, cwd=root, now=f"2026-06-16T12:00:0{index}-0500")

            events = sorted((root / "run/codex-precompact-continuity/events").glob("*.json"))
            self.assertLessEqual(len(events), 3)
            latest_event = self._event_path(root, last_payload)
            self.assertTrue(latest_event.exists())

    def test_session_snapshot_retention_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(continuity_hook, "MAX_SESSION_SNAPSHOTS", 2):
            root = self._init_repo(Path(tmp))
            last_payload = {}
            for index in range(4):
                last_payload = {
                    "hook_event_name": "PreCompact",
                    "trigger": "manual",
                    "thread_id": f"thread-{index}",
                }
                continuity_hook.run(last_payload, cwd=root, now=f"2026-06-16T12:00:0{index}-0500")

            sessions = sorted(
                path for path in (root / "run/codex-precompact-continuity/sessions").iterdir() if path.is_dir()
            )
            self.assertLessEqual(len(sessions), 2)
            self.assertTrue(self._session_latest_json(root, last_payload).exists())

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
        parsed = tomllib.loads(config)
        self.assertIn("[[hooks.PreCompact]]", config)
        self.assertIn('matcher = "manual|auto"', config)
        self.assertIn("[[hooks.SessionStart]]", config)
        self.assertIn('matcher = "compact"', config)
        self.assertIn("contextforge_precompact_continuity.py", config)
        self.assertNotIn("compact_prompt", config)
        self.assertNotIn("experimental_compact_prompt_file", config)
        self.assertNotIn("model_auto_compact_token_limit", config)
        helper = parsed["mcp_servers"]["contextforge-helper"]
        self.assertEqual(str(CONFIG_CONTRACT_ROOT / ".venv/bin/python"), helper["command"])
        self.assertEqual([str(CONFIG_CONTRACT_ROOT / "scripts/contextforge_helper_mcp.py")], helper["args"])

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

    def _session_latest_json(self, root: Path, payload: dict[str, str]) -> Path:
        key = continuity_hook.session_key(payload, root)
        self.assertIsNotNone(key)
        assert key is not None
        return root / "run/codex-precompact-continuity/sessions" / key / "latest.json"

    def _event_path(self, root: Path, payload: dict[str, str]) -> Path:
        event_id = continuity_hook.stable_event_id(payload, root)
        return root / "run/codex-precompact-continuity/events" / f"{event_id}.json"


if __name__ == "__main__":
    unittest.main()
