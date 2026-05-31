from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_state as state_lib
import control_plane_contracts as contracts


class ControlPlaneProjectStateTests(unittest.TestCase):
    def workspace_project(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(dir=state_lib.WORKSPACE_ROOT)

    def test_denied_roots_are_rejected(self) -> None:
        for root in ("/", str(Path.home()), "/home/dgk/workspace"):
            with self.subTest(root=root):
                with self.assertRaises(state_lib.RootValidationError):
                    state_lib.validate_project_root(root, require_workspace=True)

    def test_explicit_denied_root_is_rejected(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises(state_lib.RootValidationError):
                state_lib.validate_project_root(root, denied_roots={root})

    def test_symlink_escape_is_rejected_before_state_read(self) -> None:
        link = state_lib.WORKSPACE_ROOT / "context-portal-project-state-symlink-escape"
        if link.exists() or link.is_symlink():
            link.unlink()
        try:
            link.symlink_to("/tmp")
            with self.assertRaises(state_lib.RootValidationError):
                state_lib.load_state(link, require_workspace=True)
        finally:
            if link.exists() or link.is_symlink():
                link.unlink()

    def test_missing_state_is_uninitialized_and_defaultable(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            self.assertIsNone(state_lib.load_state(root, require_workspace=True))
            state = state_lib.read_or_default(root, require_workspace=True)
            self.assertEqual("uninitialized", state["status"])
            self.assertEqual(0, state["meta"]["revision"])
            self.assertEqual(1, state["meta"]["schema_version"])
            self.assertEqual(state_lib.SCHEMA_URI, state["meta"]["schema_uri"])
            self.assertEqual(str(root), state["project"]["root"])
            self.assertIsNone(state["project"]["display_root"])
            self.assertIn("artifact_refs", state)
            state_lib.validate_state(state)

    def test_legacy_env_file_absent_classifies_not_present(self) -> None:
        with self.workspace_project() as tmp:
            migration = state_lib.classify_legacy_env_file(Path(tmp).resolve())
            self.assertEqual("not_present", migration.disposition)
            self.assertEqual((), migration.keys_seen)
            self.assertIsNone(migration.digest)

    def test_legacy_env_declined_imports_sticky_decline_shape(self) -> None:
        migration = state_lib.classify_legacy_env({"CONTEXTFORGE_SERENA_DECISION": "declined"})
        self.assertEqual("imported", migration.disposition)
        decision = migration.decisions["serena"]
        self.assertEqual("service", decision["decision_kind"])
        self.assertEqual("declined", decision["state"])
        self.assertIn("sticky_decline", decision["notes"])
        self.assertIsNone(decision["reopened_at"])

    def test_legacy_env_deferred_adds_migration_open_item(self) -> None:
        migration = state_lib.classify_legacy_env({"CONTEXTFORGE_SERENA_DECISION": "deferred"})
        self.assertEqual("imported", migration.disposition)
        self.assertEqual("deferred", migration.decisions["serena"]["state"])
        self.assertEqual("migration", migration.open_items[0]["type"])
        self.assertEqual("warning", migration.open_items[0]["severity"])

    def test_legacy_env_disabled_no_service_is_distinct_from_initialized(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            base = state_lib.default_state(root)
            migration = state_lib.classify_legacy_env({"CONTEXTFORGE_SERENA_DECISION": "disabled"})
            state = state_lib.apply_legacy_migration(base, migration)
            self.assertEqual("disabled", state["status"])
            self.assertNotEqual("initialized", state["status"])
            self.assertEqual("disabled", state["decisions"]["serena"]["state"])
            self.assertEqual("imported", state["migration"]["legacy_env_disposition"])
            self.assertTrue(state["migration"]["legacy_env_seen"])
            self.assertIsNotNone(state["migration"]["imported_at"])
            state_lib.validate_state(state)

    def test_legacy_env_malformed_value_classifies_conflict(self) -> None:
        migration = state_lib.classify_legacy_env({"CONTEXTFORGE_SERENA_DECISION": "maybe"})
        self.assertEqual("conflict", migration.disposition)
        self.assertEqual("migration", migration.open_items[0]["type"])
        self.assertEqual("malformed_or_conflicting_legacy_env", migration.conflicts[0]["reason"])

    def test_legacy_env_conflicting_signals_classifies_conflict(self) -> None:
        migration = state_lib.classify_legacy_env(
            {
                "CONTEXTFORGE_SERENA_DECISION": "declined",
                "CONTEXTFORGE_SERENA_PROVISION_STATUS": "created",
            }
        )
        self.assertEqual("conflict", migration.disposition)
        self.assertEqual("blocking", migration.open_items[0]["severity"])

    def test_legacy_env_absent_and_ignored_are_different(self) -> None:
        migration = state_lib.classify_legacy_env({"CONTEXTFORGE_SERENA_DECISION": "unasked"})
        self.assertEqual("ignored", migration.disposition)
        self.assertIsNotNone(migration.digest)

    def test_parse_legacy_env_text_reports_malformed_contextforge_lines(self) -> None:
        values, malformed = state_lib.parse_legacy_env_text("CONTEXTFORGE_SERENA_DECISION\nOTHER=value\n")
        self.assertEqual({}, values)
        self.assertEqual(["line 1"], malformed)
        migration = state_lib.classify_legacy_env(values, malformed=malformed)
        self.assertEqual("conflict", migration.disposition)

    def test_apply_legacy_migration_populates_rfc_migration_fields(self) -> None:
        with self.workspace_project() as tmp:
            state = state_lib.default_state(Path(tmp).resolve())
            migration = state_lib.classify_legacy_env({"CONTEXTFORGE_SERENA_DECISION": "declined"})
            migrated = state_lib.apply_legacy_migration(state, migration)
            self.assertTrue(migrated["migration"]["legacy_env_seen"])
            self.assertEqual("imported", migrated["migration"]["legacy_env_disposition"])
            self.assertIsNotNone(migrated["migration"]["legacy_env_digest"])
            self.assertEqual({}, migrated["migration"]["client_config_migrations"])
            self.assertEqual([], migrated["migration"]["conflicts"])
            state_lib.validate_state(migrated)

    def test_secret_like_fields_are_rejected(self) -> None:
        with self.workspace_project() as tmp:
            state = state_lib.default_state(Path(tmp).resolve())
            state["x_api_token"] = "redacted-but-still-a-secret-field"
            with self.assertRaises(state_lib.StateValidationError):
                state_lib.validate_state(state)

    def test_invalid_enum_is_rejected(self) -> None:
        with self.workspace_project() as tmp:
            state = state_lib.default_state(Path(tmp).resolve())
            state["status"] = "done"
            with self.assertRaises(state_lib.StateValidationError):
                state_lib.validate_state(state)

    def test_unsupported_major_schema_version_fails_safely(self) -> None:
        with self.workspace_project() as tmp:
            state = state_lib.default_state(Path(tmp).resolve())
            state["meta"]["schema_version"] = 2
            with self.assertRaises(state_lib.StateValidationError):
                state_lib.validate_state(state)

    def test_atomic_write_creates_valid_state_without_temp_files(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            state = state_lib.default_state(root)
            written = state_lib.write_state_atomic(root, state)
            path = state_lib.project_state_path(root)
            self.assertTrue(path.exists())
            self.assertEqual(written, json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual([], list(path.parent.glob("*.tmp")))
            self.assertEqual(1, written["meta"]["revision"])
            self.assertEqual(state_lib.DEFAULT_UPDATED_BY, written["meta"]["updated_by"])
            self.assertEqual(0o644, path.stat().st_mode & 0o777)

    def test_compare_and_swap_revision_mismatch_is_rejected(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            first = state_lib.write_state_atomic(root, state_lib.default_state(root))
            self.assertEqual(1, first["meta"]["revision"])
            update = json.loads(json.dumps(first))
            with self.assertRaises(state_lib.RevisionMismatchError):
                state_lib.write_state_atomic(root, update, expected_revision=99)
            second = state_lib.write_state_atomic(root, update, expected_revision=1)
            self.assertEqual(2, second["meta"]["revision"])

    def test_active_lock_blocks_write(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            lock_path = state_lib.project_state_lock_path(root)
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("active\n", encoding="utf-8")
            with self.assertRaises(state_lib.StateLockError):
                state_lib.write_state_atomic(root, state_lib.default_state(root), stale_after_seconds=3600)

    def test_stale_lock_is_recovered_deterministically(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            lock_path = state_lib.project_state_lock_path(root)
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("stale\n", encoding="utf-8")
            old = time.time() - 120
            os.utime(lock_path, (old, old))
            written = state_lib.write_state_atomic(root, state_lib.default_state(root), stale_after_seconds=1)
            self.assertEqual(1, written["meta"]["revision"])
            self.assertFalse(lock_path.exists())

    def test_state_root_mismatch_is_rejected(self) -> None:
        with self.workspace_project() as tmp, self.workspace_project() as other:
            root = Path(tmp).resolve()
            state = state_lib.default_state(Path(other).resolve())
            with self.assertRaises(state_lib.StateValidationError):
                state_lib.write_state_atomic(root, state)

    def test_validate_state_root_uses_project_root_field(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            state = state_lib.default_state(root)
            state["project"]["root"] = "/tmp/not-this-project"
            with self.assertRaises(state_lib.StateValidationError):
                state_lib.validate_state_root(state, root)

    def test_project_state_accepts_contract_artifact_snapshot_refs(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            state = state_lib.default_state(root)
            contract = {
                "card_id": "card-context7",
                "service_family": "context7",
            }
            state["artifact_refs"]["contract_cards"].append(
                contracts.artifact_ref(
                    "contextforge://control-plane/service-bindings/context7/v1",
                    contract,
                    resolved_at="2026-05-30T21:00:00Z",
                    catalog_revision_or_etag="rev-1",
                )
            )
            state_lib.validate_state(state)


if __name__ == "__main__":
    unittest.main()
