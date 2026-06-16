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
import control_plane_contextforge_binding as binding


CONSENT_REFS = ["run/consent-receipts/receipt-project-local-config.json"]


def service_descriptor(name: str = "context7") -> dict[str, object]:
    return {
        "service_family": name,
        "canonical_service": name,
        "service_binding": f"{name}:canonical",
        "codex_alias": name.replace("-", "_"),
        "instantiation_class": "shared_canonical",
        "backend_instance": f"server-instances/{name}",
        "virtual_server": f"{name.replace('-', '_')}_server",
        "contextforge_readback_status": "matched",
        "gateway": f"{name}-gateway",
        "validation_policy": {"mode": "read_only_lookup", "default_safe_operations": ["read"]},
        "non_actions": ["do not create a per-project backend"],
    }


class ControlPlaneProjectStateTests(unittest.TestCase):
    def workspace_project(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(dir=state_lib.WORKSPACE_ROOT)

    def test_denied_roots_are_rejected(self) -> None:
        for root in ("/", str(Path.home()), "/home/dgk/workspace"):
            with self.subTest(root=root):
                with self.assertRaises(state_lib.RootValidationError):
                    state_lib.validate_project_root(root, require_workspace=True)

    def test_cmu_math_foundations_root_is_safe(self) -> None:
        root = state_lib.CMU_MATH_FOUNDATIONS_ROOT
        self.assertTrue(state_lib.is_safe_project_root(root))
        self.assertEqual(root, state_lib.validate_project_root(root, require_workspace=True))
        self.assertEqual(root / "dev", state_lib.validate_project_root(root / "dev", require_workspace=True))

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
            inspection = state_lib.inspect_project_init_state(root, require_workspace=True)
            self.assertEqual("missing", inspection["lifecycle_status"])
            self.assertEqual("fresh_initialization", inspection["recommended_action"])
            self.assertFalse(inspection["should_suppress_hook"])
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

    def test_project_init_inspector_suppresses_initialized_disabled_and_unverified_completion(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            initialized = state_lib.default_state(root, status="initialized")
            state_lib.write_state_atomic(root, initialized)
            inspection = state_lib.inspect_project_init_state(root, require_workspace=True)
            self.assertEqual("valid", inspection["lifecycle_status"])
            self.assertEqual("completed_verified", inspection["hook_prompt_state"])
            self.assertTrue(inspection["should_suppress_hook"])

            disabled = state_lib.load_state(root, require_workspace=True)
            assert disabled is not None
            disabled["status"] = "disabled"
            state_lib.write_state_atomic(root, disabled)
            inspection = state_lib.inspect_project_init_state(root, require_workspace=True)
            self.assertEqual("disabled", inspection["hook_prompt_state"])
            self.assertTrue(inspection["should_suppress_hook"])

            unverified = state_lib.load_state(root, require_workspace=True)
            assert unverified is not None
            unverified["status"] = "in_progress"
            unverified["project_init"]["x_hook_prompt_state"] = "completed_unverified"
            state_lib.write_state_atomic(root, unverified)
            inspection = state_lib.inspect_project_init_state(root, require_workspace=True)
            self.assertEqual("completed_unverified", inspection["hook_prompt_state"])
            self.assertTrue(inspection["should_suppress_hook"])

    def test_project_init_inspector_distinguishes_pending_repairable_and_blocked_state(self) -> None:
        with self.workspace_project() as tmp, self.workspace_project() as other:
            root = Path(tmp).resolve()
            pending = state_lib.default_state(root, status="in_progress")
            state_lib.write_state_atomic(root, pending)
            inspection = state_lib.inspect_project_init_state(root, require_workspace=True)
            self.assertEqual("valid", inspection["lifecycle_status"])
            self.assertEqual("resume_validation", inspection["recommended_action"])
            self.assertFalse(inspection["should_suppress_hook"])

            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="pending_choice")
            repairable = state_lib.apply_project_init_activation_to_state(
                state_lib.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            repairable.pop("project_init")
            state_lib.project_state_path(root).write_text(json.dumps(repairable), encoding="utf-8")
            inspection = state_lib.inspect_project_init_state(root, require_workspace=True)
            self.assertEqual("invalid_repairable", inspection["lifecycle_status"])
            self.assertEqual("repair_project_init_state", inspection["recommended_action"])
            self.assertTrue(inspection["root_matches"])
            self.assertFalse(inspection["project_init_present"])

            blocked = json.loads(json.dumps(repairable))
            blocked["project"]["root"] = str(Path(other).resolve())
            state_lib.project_state_path(root).write_text(json.dumps(blocked), encoding="utf-8")
            inspection = state_lib.inspect_project_init_state(root, require_workspace=True)
            self.assertEqual("invalid_blocked", inspection["lifecycle_status"])
            self.assertEqual("blocked_repair", inspection["recommended_action"])
            self.assertFalse(inspection["root_matches"])

    def test_project_init_client_states_track_independent_client_lifecycles(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            codex_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            codex_state = state_lib.apply_project_init_activation_to_state(
                state_lib.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=codex_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="validate_now", target_client="codex"),
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": True}},
                consent_receipt_refs=CONSENT_REFS,
            )
            self.assertEqual("verified", codex_state["project_init"]["client_states"]["codex"]["status"])
            self.assertEqual("completed_verified", state_lib.client_hook_prompt_state_for(codex_state, "codex"))
            self.assertEqual("active", state_lib.client_hook_prompt_state_for(codex_state, "gemini"))

            gemini_plan = binding.plan_project_init_gemini_config_write(root, [service])
            gemini_state = state_lib.apply_project_init_activation_to_state(
                codex_state,
                [service],
                target_client="gemini",
                client_config_plan=gemini_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="pending_choice", target_client="gemini"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            service_state = gemini_state["services"]["context7:canonical"]
            self.assertEqual({"codex", "gemini"}, set(service_state["target_clients"]))
            self.assertEqual("shared_contextforge_service", service_state["lifecycle"]["activation"])
            self.assertEqual("verified", gemini_state["project_init"]["client_states"]["codex"]["status"])
            self.assertEqual("reload_required", gemini_state["project_init"]["client_states"]["gemini"]["status"])
            self.assertEqual("completed_verified", state_lib.client_hook_prompt_state_for(gemini_state, "codex"))
            self.assertEqual("active", state_lib.client_hook_prompt_state_for(gemini_state, "gemini"))
            self.assertEqual(
                gemini_state["project_init"]["client_states"]["gemini"]["current_job_id"],
                state_lib.project_init_current_job_id_for_client(gemini_state, "gemini"),
            )
            self.assertEqual(
                gemini_state["project_init"]["client_states"]["codex"]["current_job_id"],
                state_lib.project_init_current_job_id_for_client(gemini_state, "codex"),
            )

            opencode_plan = binding.plan_project_init_opencode_config_write(root, [service])
            opencode_state = state_lib.apply_project_init_activation_to_state(
                gemini_state,
                [service],
                target_client="opencode",
                client_config_plan=opencode_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="pending_choice", target_client="opencode"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            service_state = opencode_state["services"]["context7:canonical"]
            self.assertEqual({"codex", "gemini", "opencode"}, set(service_state["target_clients"]))
            self.assertEqual("shared_contextforge_service", service_state["lifecycle"]["activation"])
            self.assertEqual("reload_required", opencode_state["project_init"]["client_states"]["opencode"]["status"])
            self.assertEqual("active", state_lib.client_hook_prompt_state_for(opencode_state, "opencode"))

    def test_project_init_client_states_backfill_from_existing_target_clients(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            state = state_lib.apply_project_init_activation_to_state(
                state_lib.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="validate_now", target_client="codex"),
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": True}},
                consent_receipt_refs=CONSENT_REFS,
            )
            state["project_init"].pop("client_states")
            state_lib.validate_state(state)

            self.assertIn("client_states", state["project_init"])
            self.assertEqual("verified", state["project_init"]["client_states"]["codex"]["status"])

    def test_project_scoped_service_provisioning_survives_second_client_activation(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("serena")
            service["service_binding"] = "serena:project"
            service["instantiation_class"] = "instance_per_project"
            codex_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            codex_state = state_lib.apply_project_init_activation_to_state(
                state_lib.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=codex_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="validate_now", target_client="codex"),
                validation_results={"serena:project": {"status": "passed", "target_client_visible": True}},
                consent_receipt_refs=CONSENT_REFS,
            )
            self.assertEqual("verified", codex_state["services"]["serena:project"]["provision_status"])
            self.assertEqual("project_scoped_service_provision", codex_state["services"]["serena:project"]["lifecycle"]["activation"])

            gemini_plan = binding.plan_project_init_gemini_config_write(root, [service])
            gemini_state = state_lib.apply_project_init_activation_to_state(
                codex_state,
                [service],
                target_client="gemini",
                client_config_plan=gemini_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="pending_choice", target_client="gemini"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            service_state = gemini_state["services"]["serena:project"]

            self.assertEqual("verified", service_state["provision_status"])
            self.assertEqual("project_scoped_service_provision", service_state["lifecycle"]["activation"])
            self.assertEqual({"codex", "gemini"}, set(service_state["target_clients"]))
            self.assertEqual("passed", service_state["target_clients"]["codex"]["validation_status"])
            self.assertEqual("pending", service_state["target_clients"]["gemini"]["validation_status"])
            self.assertEqual("mixed", service_state["verification_layers"]["target_client"]["status"])

    def test_service_lifecycle_normalization_removes_client_activation_surface(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            shared = service_descriptor("context7")
            serena = service_descriptor("serena")
            serena["service_binding"] = "serena:project"
            serena["instantiation_class"] = "instance_per_project"
            config_plan = binding.plan_project_init_codex_config_write(root, [shared, serena], existing_text="")
            state = state_lib.apply_project_init_activation_to_state(
                state_lib.default_state(root),
                [shared, serena],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan([shared, serena], validation_mode="pending_choice", target_client="codex"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            state["services"]["context7:canonical"]["lifecycle"]["activation"] = "project_local_client_binding"
            state["services"]["serena:project"]["lifecycle"]["activation"] = "gemini_project_local_mcp_settings"

            state_lib.validate_state(state)

            self.assertEqual("shared_contextforge_service", state["services"]["context7:canonical"]["lifecycle"]["activation"])
            self.assertEqual("project_scoped_service_provision", state["services"]["serena:project"]["lifecycle"]["activation"])

    def test_project_scoped_duplicate_service_records_are_rejected(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("serena")
            service["service_binding"] = "serena:project"
            service["instantiation_class"] = "instance_per_project"
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            state = state_lib.apply_project_init_activation_to_state(
                state_lib.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="pending_choice", target_client="codex"),
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            duplicate = json.loads(json.dumps(state["services"]["serena:project"]))
            duplicate["service_binding"] = "serena:project-duplicate"
            duplicate.pop("x_descriptor_digest", None)
            duplicate.pop("x_service_identity", None)
            duplicate.pop("x_service_identity_id", None)
            state["services"]["serena:project-duplicate"] = duplicate

            with self.assertRaisesRegex(state_lib.StateValidationError, "duplicate project-scoped service backend"):
                state_lib.validate_state(state)


if __name__ == "__main__":
    unittest.main()
