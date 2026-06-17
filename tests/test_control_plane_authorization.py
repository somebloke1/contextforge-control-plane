from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_authorization as auth
import control_plane_contracts as contracts
import control_plane_project_state as project_state


PROJECT_ROOT = "/home/dgk/workspace/legacy-controlplane-archive"
STAMP = "2026-05-30T21:00:00Z"
FUTURE = "2026-05-31T21:00:00Z"
PAST = "2026-05-29T21:00:00Z"


def base_state(*, revision: int = 7, status: str = "uninitialized") -> dict[str, object]:
    return {
        "meta": {"revision": revision},
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "cf-controlplane"},
        "status": status,
        "decisions": {},
        "services": {},
        "client_trust": {},
        "open_items": [],
    }


def base_plan(*, state: dict[str, object] | None = None, target_digest: str = "sha256:client-digest") -> dict[str, object]:
    state = copy.deepcopy(state or base_state())
    descriptor_digest = auth.stable_digest({"service_family": "serena"})
    return {
        "schema_version": 1,
        "surface": "propose_project_init",
        "planner": "control_plane_project_planner",
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "cf-controlplane"},
        "plan_id": "project-init-fixture",
        "status": "planned_non_mutating",
        "mutation_allowed": False,
        "required_consent_classes": ["project_state_write", "project_local_config_write", "service_provision"],
        "forbidden_project_init_consent_classes": sorted(auth.FORBIDDEN_GENERIC_PROJECT_INIT_CLASSES),
        "stale_plan_inputs": {
            "project_root": PROJECT_ROOT,
            "project_root_hash": project_state.project_root_hash(PROJECT_ROOT),
            "base_project_state": {
                "present": True,
                "revision": state["meta"]["revision"],  # type: ignore[index]
                "status": state["status"],
                "digest": auth.stable_digest(state),
            },
            "catalog": {"revision_or_etag": "catalog-r1", "digest": auth.stable_digest({"revision": "catalog-r1"})},
            "selected_service_descriptors": [
                {"descriptor_id": "serena", "artifact_digest": descriptor_digest, "service_family": "serena"}
            ],
            "target_client_digests": {"codex": target_digest},
            "trust_state_digest": "sha256:trust-digest",
            "drift_findings": [],
        },
        "plan_steps": [
            {
                "step_id": "plan-serena",
                "operation": "plan_project_scoped_service_provision",
                "service_binding": "serena:project",
                "required_consent_classes": ["service_provision"],
                "stale_plan_inputs": {},
            }
        ],
        "service_management_handoffs": [],
        "open_items": [],
        "artifact_drafts": {"contract_cards": [], "capability_capsules": []},
    }


def receipt_for(
    plan: dict[str, object],
    consent_class: str = "service_provision",
    *,
    actor: str = "user",
    source_client: str = "codex",
    auth_strength: str = "shared_token",
    expires_at: str = FUTURE,
    replay_policy: str = "same_plan_resume",
    service_binding: str | None = "serena:project",
    target_clients: list[str] | None = None,
    persistent_target: str = "systemd",
) -> dict[str, object]:
    return auth.create_consent_receipt(
        plan=plan,
        consent_class=consent_class,
        actor=actor,
        source_client=source_client,
        source_client_auth_strength=auth_strength,
        approval_event_ref="transcript:fixture",
        approval_evidence="redacted approval summary",
        expires_at=expires_at,
        approved_at=STAMP,
        replay_policy=replay_policy,
        scope={
            "project_root": PROJECT_ROOT,
            "service_binding": service_binding,
            "target_clients": target_clients or ["codex"],
            "persistent_target": persistent_target,
        },
    )


class ControlPlaneAuthorizationTests(unittest.TestCase):
    def test_consent_receipt_validates_and_binds_scope_actor_expiry_replay(self) -> None:
        plan = base_plan()
        receipt = receipt_for(plan)

        contracts.validate_artifact("consent_receipt", receipt)
        self.assertEqual("service_provision", receipt["consent_class"])
        self.assertEqual(auth.plan_digest(plan), receipt["plan_digest"])
        self.assertEqual("user", receipt["actor"])
        self.assertEqual("codex", receipt["source_client"])
        self.assertEqual(FUTURE, receipt["expires_at"])
        self.assertEqual("same_plan_resume", receipt["replay_policy"])
        self.assertEqual(PROJECT_ROOT, receipt["scope"]["project_root"])  # type: ignore[index]
        self.assertEqual(["codex"], receipt["scope"]["x_target_clients"])  # type: ignore[index]

    def test_generic_project_init_cannot_authorize_separate_workflow_classes(self) -> None:
        plan = base_plan()
        for operation_class in [
            "user_global_client_trust",
            "catalog_promotion",
            "token_material_change",
            "secret_value_write",
            "network_exposure_change",
        ]:
            with self.subTest(operation_class=operation_class):
                decision = auth.authorize_operation(
                    plan=plan,
                    operation_class=operation_class,
                    actor="user",
                    workflow_identity="project_init",
                    source_client="codex",
                    source_client_auth_strength="per_client_token",
                    target_clients=["codex"],
                    project_root=PROJECT_ROOT,
                    current_state=base_state(),
                    current_target_client_digests={"codex": "sha256:client-digest"},
                    current_trust_digest="sha256:trust-digest",
                    current_catalog_revision_or_etag="catalog-r1",
                    receipts=[],
                    approval_workflow="project_init",
                    now=STAMP,
                )
                self.assertEqual("block", decision["decision"])
                self.assertIn("requires a separate explicit workflow", " ".join(decision["reasons"]))

    def test_unauthorized_caller_source_client_and_auth_strength_block(self) -> None:
        plan = base_plan()
        receipt = receipt_for(plan, actor="user", source_client="codex", auth_strength="asserted")

        decision = auth.authorize_operation(
            plan=plan,
            operation_class="service_provision",
            actor="assistant",
            workflow_identity="project_init",
            source_client="claude",
            source_client_auth_strength="asserted",
            target_clients=["codex"],
            project_root=PROJECT_ROOT,
            current_state=base_state(),
            current_target_client_digests={"codex": "sha256:client-digest"},
            current_trust_digest="sha256:trust-digest",
            current_catalog_revision_or_etag="catalog-r1",
            service_binding="serena:project",
            persistent_target="systemd",
            receipts=[receipt],
            allowed_callers=["user"],
            allowed_workflows=["project_init"],
            now=STAMP,
        )

        self.assertEqual("block", decision["decision"])
        self.assertIn("caller is not authorized", " ".join(decision["reasons"]))
        self.assertIn("source-client auth strength is insufficient", " ".join(decision["reasons"]))
        self.assertIn("missing consent receipt", " ".join(decision["reasons"]))

    def test_expired_receipt_and_scope_mismatch_block_replay_or_apply(self) -> None:
        plan = base_plan()
        expired = receipt_for(plan, expires_at=PAST)
        wrong_scope = receipt_for(plan, service_binding="other:service")
        null_service_scope = receipt_for(plan, service_binding=None, target_clients=["codex"])

        expired_check = auth.validate_consent_receipt(
            expired,
            plan=plan,
            operation_class="service_provision",
            actor="user",
            source_client="codex",
            project_root=PROJECT_ROOT,
            service_binding="serena:project",
            target_clients=["codex"],
            persistent_target="systemd",
            replay_intent="resume",
            now=STAMP,
        )
        mismatch_check = auth.validate_consent_receipt(
            wrong_scope,
            plan=plan,
            operation_class="service_provision",
            actor="user",
            source_client="codex",
            project_root=PROJECT_ROOT,
            service_binding="serena:project",
            target_clients=["codex"],
            persistent_target="systemd",
            replay_intent="resume",
            now=STAMP,
        )
        null_scope_check = auth.validate_consent_receipt(
            null_service_scope,
            plan=plan,
            operation_class="service_provision",
            actor="user",
            source_client="codex",
            project_root=PROJECT_ROOT,
            service_binding="other:service",
            target_clients=["codex"],
            persistent_target="systemd",
            replay_intent="resume",
            now=STAMP,
        )

        self.assertEqual("block", expired_check["decision"])
        self.assertIn("expired", " ".join(expired_check["reasons"]))
        self.assertEqual("block", mismatch_check["decision"])
        self.assertIn("service binding scope", " ".join(mismatch_check["reasons"]))
        self.assertEqual("block", null_scope_check["decision"])
        self.assertIn("service binding scope", " ".join(null_scope_check["reasons"]))

    def test_tampered_consent_receipt_fails_integrity_check(self) -> None:
        plan = base_plan()
        receipt = receipt_for(plan)
        tampered = copy.deepcopy(receipt)
        tampered["expires_at"] = FUTURE.replace("31", "30")

        check = auth.validate_consent_receipt(
            tampered,
            plan=plan,
            operation_class="service_provision",
            actor="user",
            source_client="codex",
            project_root=PROJECT_ROOT,
            service_binding="serena:project",
            target_clients=["codex"],
            persistent_target="systemd",
            replay_intent="resume",
            now=STAMP,
        )

        self.assertEqual("block", check["decision"])
        self.assertIn("receipt integrity check failed", check["reasons"])

    def test_stale_state_revision_or_target_client_digest_blocks(self) -> None:
        plan = base_plan()

        revision_stale = auth.validate_stale_plan(
            plan,
            current_state=base_state(revision=8),
            project_root=PROJECT_ROOT,
            current_target_client_digests={"codex": "sha256:client-digest"},
            current_trust_digest="sha256:trust-digest",
            current_catalog_revision_or_etag="catalog-r1",
        )
        target_stale = auth.validate_stale_plan(
            plan,
            current_state=base_state(),
            project_root=PROJECT_ROOT,
            current_target_client_digests={"codex": "sha256:changed"},
            current_trust_digest="sha256:trust-digest",
            current_catalog_revision_or_etag="catalog-r1",
        )

        self.assertEqual("block", revision_stale["decision"])
        self.assertIn("project state revision changed", revision_stale["reasons"])
        self.assertEqual("block", target_stale["decision"])
        self.assertIn("target client digest changed: codex", target_stale["reasons"])

    def test_same_plan_resume_with_compatible_replay_policy_is_allowed(self) -> None:
        plan = base_plan()
        receipt = receipt_for(plan, replay_policy="same_plan_resume")

        decision = auth.authorize_operation(
            plan=plan,
            operation_class="service_provision",
            actor="user",
            workflow_identity="project_init",
            source_client="codex",
            source_client_auth_strength="shared_token",
            target_clients=["codex"],
            project_root=PROJECT_ROOT,
            current_state=base_state(),
            current_target_client_digests={"codex": "sha256:client-digest"},
            current_trust_digest="sha256:trust-digest",
            current_catalog_revision_or_etag="catalog-r1",
            service_binding="serena:project",
            persistent_target="systemd",
            receipts=[receipt],
            replay_intent="resume",
            allowed_callers=["user"],
            allowed_workflows=["project_init"],
            now=STAMP,
        )

        self.assertEqual("resume", decision["decision"])
        self.assertTrue(decision["allowed"])

    def test_project_local_config_preflight_is_idempotent_and_blocks_unmanaged_block(self) -> None:
        plan = base_plan()
        receipt = receipt_for(
            plan,
            "project_local_config_write",
            persistent_target="file",
            service_binding=None,
        )
        desired = {"mcpServers": {"contextforge": {"type": "sse", "url": "http://127.0.0.1:4444/sse"}}}
        owned_block = {
            "name": "contextforge-control-plane",
            "managed_by": "contextforge-control-plane",
            "content": desired,
        }
        unmanaged_block = {
            "name": "contextforge-control-plane",
            "managed_by": "manual-user-edit",
            "content": {"mcpServers": {"contextforge": {"type": "stdio"}}},
        }

        noop = auth.project_local_apply_preflight(
            operation_class="project_local_config_write",
            project_root=PROJECT_ROOT,
            target_path=".codex/config.toml",
            desired_content=desired,
            current_block=owned_block,
            receipt=receipt,
            plan=plan,
            replay_intent="resume",
            now=STAMP,
        )
        update = auth.project_local_apply_preflight(
            operation_class="project_local_config_write",
            project_root=PROJECT_ROOT,
            target_path=".codex/config.toml",
            desired_content={**desired, "comment": "redacted"},
            current_block=owned_block,
            receipt=receipt,
            plan=plan,
            now=STAMP,
        )
        blocked = auth.project_local_apply_preflight(
            operation_class="project_local_config_write",
            project_root=PROJECT_ROOT,
            target_path=".codex/config.toml",
            desired_content=desired,
            current_block=unmanaged_block,
            receipt=receipt,
            plan=plan,
            now=STAMP,
        )

        self.assertEqual("resume", noop["decision"])
        self.assertEqual("noop", noop["action"])
        self.assertEqual("allow", update["decision"])
        self.assertEqual("update_owned_block", update["action"])
        self.assertEqual("block", blocked["decision"])
        self.assertEqual("user_action", blocked["action"])

    def test_journal_entry_references_receipts_contracts_handoffs_and_rejects_secrets(self) -> None:
        plan = base_plan()
        receipt = receipt_for(plan)
        contract_ref = contracts.artifact_ref(
            "contextforge://control-plane/service-bindings/serena/v1",
            {"card_id": "serena-card", "redaction_status": "redacted"},
            resolved_at=STAMP,
        )
        handoff_ref = contracts.artifact_ref(
            "contextforge://control-plane/service-handoffs/serena/v1",
            {"handoff_id": "serena-handoff", "redaction_status": "redacted"},
            resolved_at=STAMP,
        )

        entry = auth.build_plan_journal_entry(
            plan=plan,
            run_id="run-fixture",
            step_id="plan-serena",
            operation_class="service_provision",
            actor="user",
            source_client="codex",
            base_revision=7,
            observed_revision=7,
            required_receipts=[receipt],
            observed_receipts=[receipt],
            service_contract_refs=[contract_ref],
            semantic_policy_refs=[],
            service_management_handoff_refs=[handoff_ref],
            redacted_output_summary={"created": False, "message": "redacted no-op"},
            status="resumed",
            replay_policy="same_plan_resume",
            recovery_outcome="resume",
            created_at=STAMP,
        )

        self.assertEqual("approved_plan_step", entry["journal_type"])
        self.assertEqual(1, len(entry["required_consent_receipts"]))
        self.assertEqual(1, len(entry["observed_consent_receipts"]))
        self.assertEqual([contract_ref], entry["service_contract_refs"])
        self.assertEqual([handoff_ref], entry["service_management_handoff_refs"])
        contracts.validate_redacted(entry, require_status=True)
        with self.assertRaises(ValueError):
            auth.build_plan_journal_entry(
                plan=plan,
                run_id="run-fixture",
                step_id="leak",
                operation_class="service_provision",
                actor="user",
                source_client="codex",
                base_revision=7,
                observed_revision=7,
                required_receipts=[receipt],
                observed_receipts=[receipt],
                redacted_output_summary={"token": "redacted"},
            )


if __name__ == "__main__":
    unittest.main()
