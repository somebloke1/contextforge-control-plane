from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_planner as planner
import control_plane_project_state as project_state


PROJECT_ROOT = "/home/dgk/workspace/context-portal"


def base_state(*, status: str = "uninitialized", decisions: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "meta": {"revision": 7},
        "project": {"root": PROJECT_ROOT, "root_hash": project_state.project_root_hash(PROJECT_ROOT), "name": "context-portal"},
        "status": status,
        "decisions": decisions or {},
        "services": {},
        "client_trust": {},
        "open_items": [],
    }


def shared_descriptor(service_family: str = "context7") -> dict[str, object]:
    return {
        "service_family": service_family,
        "canonical_service": service_family,
        "instantiation_class": "shared_canonical",
        "native_transports": ["streamable_http", "sse"],
        "scope": {"runtime_scope": "host", "resource_scope": {"scope": "documentation"}},
        "contextforge": {
            "gateway": {"name": f"{service_family}-gateway"},
            "virtual_server": {"name": f"{service_family}-server"},
        },
        "registration": {"status": "registered"},
    }


def serena_descriptor() -> dict[str, object]:
    return {
        "service_family": "serena",
        "canonical_service": "serena",
        "instantiation_class": "instance_per_project",
        "native_transports": ["stdio"],
        "scope": {"scope_type": "single_workspace_code_intelligence", "workspace_root": PROJECT_ROOT},
    }


class ControlPlaneProjectPlannerTests(unittest.TestCase):
    def test_accepted_shared_canonical_plans_bind_verify_only_with_refs(self) -> None:
        plan = planner.plan_project_initialization(
            PROJECT_ROOT,
            state=base_state(),
            catalog={"revision": "catalog-r1"},
            service_descriptors=[shared_descriptor()],
        )

        self.assertEqual("planned_non_mutating", plan["status"])
        self.assertFalse(plan["mutation_allowed"])
        self.assertEqual(["read_only_inspection"], plan["required_consent_classes"])
        step = plan["plan_steps"][0]
        self.assertEqual("context7:canonical", step["service_binding"])
        self.assertEqual("shared_canonical", step["instantiation_class"])
        self.assertEqual("bind_verify_existing_shared_service", step["operation"])
        self.assertEqual(["read_only_inspection"], step["required_consent_classes"])
        self.assertIsNotNone(step["contract_card_ref"])
        self.assertIsNotNone(step["capability_capsule_ref"])
        self.assertIn("no per-project backend", step["non_actions"])
        self.assertIn("no per-project server-instance directory", step["non_actions"])
        self.assertEqual([], step["effect_summary"]["mutation_classes"])
        self.assertFalse(step["effect_summary"]["service_provision"])
        self.assertFalse(step["effect_summary"]["project_state_service_record"])
        self.assertEqual("existing_only", step["effect_summary"]["contextforge_gateway"])
        self.assertIn("verify ContextForge /mcp endpoint where exposed", step["verification_requirements"])
        self.assertEqual([], plan["service_management_handoffs"])

    def test_serena_declined_decision_yields_no_service_open_item(self) -> None:
        state = base_state(
            decisions={
                "serena": {
                    "decision_kind": "service",
                    "state": "declined",
                    "service_binding": "serena:project",
                    "contract_card_ref": None,
                    "decided_at": None,
                    "decided_by": "fixture",
                    "source_plan_id": None,
                    "reopened_at": None,
                    "notes": "fixture decline",
                }
            }
        )

        plan = planner.plan_project_initialization(PROJECT_ROOT, state=state, service_descriptors=[serena_descriptor()])

        self.assertEqual([], plan["plan_steps"])
        self.assertEqual("blocked_open_items", plan["status"])
        self.assertEqual("no_service", plan["open_items"][0]["detail"]["status"])
        self.assertEqual("2026-05-30T00:00:00Z", plan["open_items"][0]["created_at"])
        self.assertTrue(plan["open_items"][0]["detail"]["sticky"])
        self.assertNotIn("service_provision", plan["required_consent_classes"])

    def test_disabled_project_state_yields_non_mutating_disabled_plan(self) -> None:
        plan = planner.plan_project_initialization(
            PROJECT_ROOT,
            state=base_state(status="disabled"),
            service_descriptors=[shared_descriptor()],
        )

        self.assertEqual("disabled_no_service", plan["status"])
        self.assertFalse(plan["mutation_allowed"])
        self.assertEqual([], plan["plan_steps"])
        self.assertEqual([], plan["required_consent_classes"])
        self.assertEqual("project-init-disabled", plan["open_items"][0]["id"])

    def test_candidate_descriptor_yields_handoff_without_catalog_or_state_effects(self) -> None:
        candidate = {
            "candidate": True,
            "service_family": "invoiceapi",
            "canonical_service": "invoiceapi",
            "backend": {"transport": "stdio", "command": "invoice-mcp"},
            "scope": {"runtime_scope": "host", "resource_scope": {"scope": "invoices"}},
        }

        plan = planner.plan_project_initialization(PROJECT_ROOT, state=base_state(), service_descriptors=[candidate])

        self.assertEqual([], plan["plan_steps"])
        self.assertEqual(1, len(plan["service_management_handoffs"]))
        handoff = plan["service_management_handoffs"][0]
        self.assertEqual("service_management_plan", handoff["required_next_workflow"])
        self.assertIn("catalog_promotion", handoff["forbidden_under_current_approval"])
        self.assertIn("project_state_service_record", handoff["forbidden_under_current_approval"])
        self.assertEqual("handoff_required", plan["open_items"][0]["type"])

    def test_missing_trust_and_language_are_blocking_without_global_trust_consent(self) -> None:
        plan = planner.plan_project_initialization(
            PROJECT_ROOT,
            state=base_state(),
            service_descriptors=[shared_descriptor()],
            missing_trust=[{"client": "codex", "reason": "project trust not approved"}],
            missing_language=["python"],
        )

        item_types = {item["type"] for item in plan["open_items"]}
        self.assertIn("trust", item_types)
        self.assertIn("language_profile_missing", item_types)
        self.assertEqual("blocked_open_items", plan["status"])
        self.assertNotIn("user_global_client_trust", plan["required_consent_classes"])
        self.assertIn("user_global_client_trust", plan["forbidden_project_init_consent_classes"])

    def test_stale_inputs_include_revision_root_catalog_and_digest_snapshots(self) -> None:
        descriptor = shared_descriptor()
        plan = planner.plan_project_initialization(
            PROJECT_ROOT,
            state=base_state(),
            catalog={"etag": "catalog-e1"},
            service_descriptors=[descriptor],
            target_client_digests={"codex": "sha256:client-digest"},
            trust_state_digest="sha256:trust-digest",
            drift_findings=[{"id": "stale-catalog", "severity": "warning"}],
        )

        stale_inputs = plan["stale_plan_inputs"]
        self.assertEqual(project_state.project_root_hash(PROJECT_ROOT), stale_inputs["project_root_hash"])
        self.assertEqual(7, stale_inputs["base_project_state"]["revision"])
        self.assertEqual("catalog-e1", stale_inputs["catalog"]["revision_or_etag"])
        self.assertEqual("sha256:client-digest", stale_inputs["target_client_digests"]["codex"])
        self.assertEqual("sha256:trust-digest", stale_inputs["trust_state_digest"])
        self.assertEqual("sha256:", stale_inputs["selected_service_descriptors"][0]["artifact_digest"][:7])
        step_inputs = plan["plan_steps"][0]["stale_plan_inputs"]
        self.assertEqual("catalog-e1", step_inputs["catalog_revision_or_etag"])
        self.assertEqual("sha256:client-digest", step_inputs["target_client_digests"]["codex"])
        self.assertEqual("sha256:trust-digest", step_inputs["trust_state_digest"])
        self.assertEqual("drift", plan["open_items"][0]["type"])

    def test_planner_does_not_create_state_file_or_mutate_injected_inputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = str(Path(tmp).resolve())
            state = base_state()
            state["project"] = {
                "root": root,
                "root_hash": project_state.project_root_hash(root),
                "name": Path(root).name,
            }
            catalog = {"revision": "catalog-r1"}
            descriptor = shared_descriptor()
            original_state = copy.deepcopy(state)
            original_catalog = copy.deepcopy(catalog)
            original_descriptor = copy.deepcopy(descriptor)
            state_path = project_state.project_state_path(root)
            self.assertFalse(state_path.exists())

            planner.plan_project_initialization(
                root,
                state=state,
                catalog=catalog,
                service_descriptors=[descriptor],
                target_client_digests={"codex": "sha256:client-digest"},
            )

            self.assertFalse(state_path.exists())
            self.assertEqual(original_state, state)
            self.assertEqual(original_catalog, catalog)
            self.assertEqual(original_descriptor, descriptor)

    def test_planner_does_not_create_state_file_for_repo_with_existing_state(self) -> None:
        state = base_state()
        catalog = {"revision": "catalog-r1"}
        descriptor = shared_descriptor()
        original_state = copy.deepcopy(state)
        original_catalog = copy.deepcopy(catalog)
        original_descriptor = copy.deepcopy(descriptor)
        state_path = project_state.project_state_path(PROJECT_ROOT)
        existed_before = state_path.exists()

        planner.plan_project_initialization(
            PROJECT_ROOT,
            state=state,
            catalog=catalog,
            service_descriptors=[descriptor],
            target_client_digests={"codex": "sha256:client-digest"},
        )

        self.assertEqual(existed_before, state_path.exists())
        self.assertEqual(original_state, state)
        self.assertEqual(original_catalog, catalog)
        self.assertEqual(original_descriptor, descriptor)


if __name__ == "__main__":
    unittest.main()
