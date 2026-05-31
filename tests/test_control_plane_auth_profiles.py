from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_auth_profiles as profiles
import control_plane_authorization as authorization
import control_plane_project_state as project_state


PROJECT_ROOT = "/home/dgk/workspace/context-portal"
STAMP = "2026-05-30T23:00:00Z"
FUTURE = "2026-05-31T23:00:00Z"
PAST = "2026-05-29T23:00:00Z"
RAW_TOKEN = "Bearer " + ("T" * 32)


def base_plan() -> dict[str, object]:
    state = {
        "meta": {"revision": 1},
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "context-portal"},
        "status": "uninitialized",
        "decisions": {},
        "services": {},
        "client_trust": {},
        "open_items": [],
    }
    return {
        "schema_version": 1,
        "surface": "token_lifecycle",
        "planner": "control_plane_auth_profiles",
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "context-portal"},
        "plan_id": "token-lifecycle-fixture",
        "status": "planned_non_mutating",
        "mutation_allowed": False,
        "required_consent_classes": ["token_material_change"],
        "stale_plan_inputs": {
            "project_root": PROJECT_ROOT,
            "project_root_hash": project_state.project_root_hash(PROJECT_ROOT),
            "base_project_state": {
                "present": True,
                "revision": state["meta"]["revision"],  # type: ignore[index]
                "status": state["status"],
                "digest": authorization.stable_digest(state),
            },
            "catalog": {"revision_or_etag": "catalog-r1", "digest": authorization.stable_digest({"revision": "catalog-r1"})},
            "selected_service_descriptors": [],
            "target_client_digests": {"codex": "sha256:client-digest"},
            "trust_state_digest": "sha256:trust-digest",
            "drift_findings": [],
        },
        "plan_steps": [
            {
                "step_id": "rotate-local-assistant-token",
                "operation": "token_lifecycle",
                "required_consent_classes": ["token_material_change"],
                "stale_plan_inputs": {},
            }
        ],
        "service_management_handoffs": [],
        "open_items": [],
        "artifact_drafts": {"contract_cards": [], "capability_capsules": []},
    }


def token_receipt(plan: dict[str, object], *, approved_at: str = STAMP, expires_at: str = FUTURE) -> dict[str, object]:
    return authorization.create_consent_receipt(
        plan=plan,
        consent_class="token_material_change",
        actor="user",
        source_client="codex",
        source_client_auth_strength="per_client_token",
        approval_event_ref="transcript:redacted-token-approval",
        approval_evidence="redacted token lifecycle approval",
        approved_at=approved_at,
        expires_at=expires_at,
        replay_policy="fresh_approval_required",
        scope={
            "project_root": PROJECT_ROOT,
            "service_binding": None,
            "target_clients": ["codex"],
            "persistent_target": "token-store",
        },
    )


def redaction_surfaces(*, leak: bool = False) -> dict[str, object]:
    safe = {
        "redaction_status": "redacted",
        "summary": "token material not included",
        "token_source": "restrictive_local_file",
        "token_path": "config/contextforge.env",
        "evidence": "<redacted>",
    }
    surfaces = {surface: copy.deepcopy(safe) for surface in profiles.REQUIRED_TOKEN_REDACTION_SURFACES}
    surfaces["command_arguments"] = {"argv": ["contextforge-wrapper", "--token-file", "config/contextforge.env"]}
    surfaces["normal_logs"] = {"redaction_status": "redacted", "lines": ["request authenticated with redacted token metadata"]}
    if leak:
        surfaces["audit_records"] = {"redaction_status": "redacted", "line": f"Authorization: {RAW_TOKEN}"}
    return surfaces


class ControlPlaneAuthProfileTests(unittest.TestCase):
    def test_loopback_authenticated_http_passes_for_loopback_bearer_binds(self) -> None:
        decision = profiles.validate_loopback_bind_observations(
            [
                {"url": "http://127.0.0.1:4444/mcp", "auth_scheme": "bearer"},
                {"bind": "[::1]:4444", "http_requires_bearer": True},
            ]
        )

        self.assertEqual("allow", decision["decision"])
        self.assertTrue(decision["local_success"])
        self.assertFalse(decision["network_exposure_workflow_required"])

    def test_wildcard_or_public_bind_blocks_local_success_and_requires_remote_workflow(self) -> None:
        for bind in ["0.0.0.0:4444", "http://192.0.2.10:4444/sse"]:
            with self.subTest(bind=bind):
                decision = profiles.validate_loopback_bind_observations([{"bind": bind, "auth_scheme": "bearer"}])

                self.assertEqual("block", decision["decision"])
                self.assertFalse(decision["local_success"])
                self.assertTrue(decision["network_exposure_workflow_required"])
                self.assertEqual("network_exposure_change", decision["required_remote_consent_class"])

    def test_missing_bearer_auth_evidence_blocks_loopback_success(self) -> None:
        decision = profiles.validate_loopback_bind_observations([{"bind": "127.0.0.1:4444"}])

        self.assertEqual("block", decision["decision"])
        self.assertFalse(decision["local_success"])
        self.assertIn("authenticated bearer HTTP", " ".join(decision["reasons"]))

    def test_local_assistant_token_profile_requires_least_privilege_negative_denials(self) -> None:
        token_profile = {
            "admin": False,
            "allowed_virtual_servers": ["project-inspector:context-portal"],
            "allowed_workflows": ["read_only_inspection", "propose_project_init", "verify_project_binding"],
            "allowed_operations": ["virtual_server:project-inspector:context-portal:list_tools"],
            "denied_operations": sorted(profiles.FORBIDDEN_LOCAL_TOKEN_OPERATION_CLASSES),
            "negative_probes": [
                {"operation": "catalog_crud", "allowed": False},
                {"operation": "token_admin", "allowed": False},
                {"operation": "unapproved_apply", "allowed": False},
                {"operation": "virtual_server:other-project:call_tool", "allowed": False},
                {"operation": "remote_only_workflow", "allowed": False},
            ],
        }
        decision = profiles.validate_local_assistant_token_profile(
            token_profile,
            approved_virtual_servers=["project-inspector:context-portal"],
        )

        self.assertEqual("allow", decision["decision"])
        self.assertTrue(all(result["status"] in {"passed", "not_applicable"} for result in decision["negative_probe_results"]))

    def test_local_assistant_token_profile_blocks_admin_catalog_token_and_unrelated_access(self) -> None:
        token_profile = {
            "is_admin": True,
            "allowed_virtual_servers": ["project-inspector:context-portal", "other-project"],
            "allowed_workflows": ["read_only_inspection", "remote_only_workflow"],
            "allowed_operations": ["catalog_crud", "token_admin", "unapproved_apply"],
            "negative_probes": [{"operation": "catalog_crud", "allowed": True}],
        }
        decision = profiles.validate_local_assistant_token_profile(
            token_profile,
            approved_virtual_servers=["project-inspector:context-portal"],
        )

        self.assertEqual("block", decision["decision"])
        self.assertIn("non-admin", " ".join(decision["reasons"]))
        self.assertIn("unapproved virtual-server", " ".join(decision["reasons"]))
        self.assertIn("forbidden local assistant token permission", " ".join(decision["reasons"]))
        self.assertIn("negative probe allowed forbidden operation", " ".join(decision["reasons"]))

    def test_token_rotation_and_revocation_require_token_material_consent_and_per_client_strength(self) -> None:
        plan = base_plan()
        receipt = token_receipt(plan)
        rotation = profiles.validate_token_lifecycle_workflow(
            action="rotate",
            source_client_auth_strength="per_client_token",
            consent_receipts=[receipt],
            redaction_surfaces=redaction_surfaces(),
            raw_token_materials=[RAW_TOKEN],
            plan=plan,
            actor="user",
            source_client="codex",
            project_root=PROJECT_ROOT,
            now=STAMP,
        )
        revocation_without_consent = profiles.validate_token_lifecycle_workflow(
            action="revoke",
            source_client_auth_strength="per_client_token",
            consent_receipts=[],
            redaction_surfaces=redaction_surfaces(),
            raw_token_materials=[RAW_TOKEN],
            now=STAMP,
        )
        rotation_with_shared_auth = profiles.validate_token_lifecycle_workflow(
            action="rotate",
            source_client_auth_strength="shared_token",
            consent_receipts=[receipt],
            redaction_surfaces=redaction_surfaces(),
            raw_token_materials=[RAW_TOKEN],
            now=STAMP,
        )

        self.assertEqual("allow", rotation["decision"])
        self.assertEqual("block", revocation_without_consent["decision"])
        self.assertIn("missing token_material_change consent receipt", revocation_without_consent["reasons"])
        self.assertEqual("block", rotation_with_shared_auth["decision"])
        self.assertIn("per-client token auth strength", " ".join(rotation_with_shared_auth["reasons"]))

    def test_stale_failed_or_revoked_token_requires_fresh_approval(self) -> None:
        plan = base_plan()
        stale_receipt = token_receipt(plan, approved_at=PAST)
        fresh_receipt = token_receipt(plan, approved_at=STAMP)
        stale_blocked = profiles.validate_token_lifecycle_workflow(
            action="rotate",
            source_client_auth_strength="per_client_token",
            consent_receipts=[stale_receipt],
            redaction_surfaces=redaction_surfaces(),
            raw_token_materials=[RAW_TOKEN],
            token_state={"state": "revoked", "revoked_at": "2026-05-30T20:00:00Z"},
            now=STAMP,
        )
        fresh_allowed = profiles.validate_token_lifecycle_workflow(
            action="rotate",
            source_client_auth_strength="per_client_token",
            consent_receipts=[fresh_receipt],
            redaction_surfaces=redaction_surfaces(),
            raw_token_materials=[RAW_TOKEN],
            token_state={"state": "revoked", "revoked_at": "2026-05-30T20:00:00Z"},
            now=STAMP,
        )

        self.assertEqual("block", stale_blocked["decision"])
        self.assertIn("fresh approval required after revoked token state", stale_blocked["reasons"])
        self.assertEqual("allow", fresh_allowed["decision"])

    def test_redaction_verification_covers_required_surfaces_and_blocks_token_leaks(self) -> None:
        clean = profiles.verify_token_redaction_surfaces(redaction_surfaces(), raw_token_materials=[RAW_TOKEN])
        leaking = profiles.verify_token_redaction_surfaces(redaction_surfaces(leak=True), raw_token_materials=[RAW_TOKEN])
        missing = profiles.verify_token_redaction_surfaces({"plan_payloads": {}}, raw_token_materials=[RAW_TOKEN])

        self.assertEqual("allow", clean["decision"])
        self.assertEqual("block", leaking["decision"])
        self.assertIn("audit_records leaks token material", " ".join(leaking["reasons"]))
        self.assertEqual("block", missing["decision"])
        self.assertIn("missing redaction surface", " ".join(missing["reasons"]))
        self.assertNotIn(RAW_TOKEN, json.dumps(clean, sort_keys=True))

    def test_downstream_missing_secret_is_typed_separate_from_contextforge_client_auth(self) -> None:
        decision = profiles.classify_auth_boundary_observation(
            {
                "contextforge_client_auth": {"status": "passed"},
                "downstream_credentials": {"status": "missing", "missing_secrets": ["GITHUB_TOKEN"]},
            }
        )

        self.assertEqual("block", decision["decision"])
        self.assertTrue(decision["contextforge_client_auth_distinct_from_downstream_credentials"])
        self.assertEqual("secret", decision["blocking_items"][0]["type"])
        self.assertEqual("downstream_missing_secret", decision["blocking_items"][0]["classification"])
        self.assertNotEqual("contextforge_client_auth_failed", decision["blocking_items"][0]["classification"])


if __name__ == "__main__":
    unittest.main()
