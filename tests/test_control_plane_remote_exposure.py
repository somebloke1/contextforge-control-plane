from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_remote_exposure as remote


FIXTURE_PATH = REPO_ROOT / "tests/fixtures/control_plane_remote_exposure_cases.json"


class ControlPlaneRemoteExposureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}

    def test_fixture_names_cover_w11c_remote_gate_surface(self) -> None:
        self.assertEqual(
            {
                "default_blocked_local_profile",
                "local_shared_token_rejected",
                "missing_tls_origin_revocation_blocked",
                "allowlisted_service_pass_shape",
                "broad_serena_scope_changing_exposure_blocked",
                "denied_admin_token_secret_catalog_tools",
            },
            set(self.cases),
        )

    def test_remote_exposure_gate_fixture_outcomes(self) -> None:
        for name, case in self.cases.items():
            with self.subTest(case=name):
                plan = self.plan_for(case)
                expected = case["expected"]
                self.assertEqual(expected["decision"], plan["decision"])
                self.assertFalse(plan["mutation_performed"])
                self.assertFalse(plan["remote_profile_default"])
                self.assertEqual(remote.LOCAL_DEFAULT_AUTH_PROFILE, plan["active_local_auth_profile"])

                blockers = self.blockers_by_type(plan)
                for blocker_type in expected.get("blockers", []):
                    self.assertIn(blocker_type, blockers)

                if expected["decision"] == "intend":
                    self.assertTrue(plan["eligible_for_remote_exposure"])
                    self.assertEqual(expected["required_consent_class"], plan["required_consent_class"])
                    self.assertEqual(expected["active_local_auth_profile"], plan["local_state_reference"]["active_auth_profile"])
                    self.assertEqual(expected["local_state_status"], plan["local_state_reference"]["remote_status"])
                    self.assertEqual(
                        expected["allowed_tools"],
                        [item["tool_id"] for item in plan["tool_exposure"] if item["decision"] == "allow"],
                    )
                    self.assertTrue(plan["negative_exposure_checks"])
                    self.assertTrue(all(item["status"] == expected["negative_check_status"] for item in plan["negative_exposure_checks"]))

    def test_network_exposure_approval_is_not_substitutable(self) -> None:
        case = self.cases["default_blocked_local_profile"]
        plan = self.plan_for(case)
        blockers = self.blockers_by_type(plan)

        self.assertIn("missing_network_exposure_approval", blockers)
        self.assertIn("approval_class_not_substitutable", blockers)
        self.assertIn("project_local_config_write", blockers["approval_class_not_substitutable"]["consent_classes"])
        self.assertEqual("separate_open_item", plan["local_state_reference"]["remote_status"])
        self.assertEqual("not_default_local_verification", plan["local_state_reference"]["local_verification_role"])

    def test_network_exposure_approval_cannot_bundle_separate_workflow_classes(self) -> None:
        request = self.request_for(
            {
                "overrides": {
                    "consent_receipt_refs": [
                        *self.fixture["default_request"]["consent_receipt_refs"],
                        {
                            "ref": "contextforge://control-plane/receipts/token-change",
                            "content_digest": "sha256:7777777777777777777777777777777777777777777777777777777777777777",
                            "resolved_at": "2026-05-30T23:40:00Z",
                            "x_consent_class": "token_material_change",
                        },
                        {
                            "ref": "contextforge://control-plane/receipts/global-trust",
                            "content_digest": "sha256:8888888888888888888888888888888888888888888888888888888888888888",
                            "resolved_at": "2026-05-30T23:40:00Z",
                            "x_consent_class": "user_global_client_trust",
                        },
                    ]
                }
            }
        )
        plan = self.build_plan(request)
        blockers = self.blockers_by_type(plan)

        self.assertEqual("block", plan["decision"])
        self.assertIn("approval_class_not_substitutable", blockers)
        self.assertEqual(
            ["token_material_change", "user_global_client_trust"],
            blockers["approval_class_not_substitutable"]["consent_classes"],
        )

    def test_local_shared_or_wrapper_token_profile_is_rejected(self) -> None:
        plan = self.plan_for(self.cases["local_shared_token_rejected"])
        blockers = self.blockers_by_type(plan)

        self.assertIn("local_token_reuse_rejected", blockers)
        self.assertIn("missing_remote_token_profile", blockers)
        self.assertIn("remote_token_not_separate", blockers)
        self.assertEqual("local_shared_token", plan["remote_auth_profile"]["token_source_class"])

    def test_allowlisted_remote_profile_shape_stays_separate_from_local_success(self) -> None:
        plan = self.plan_for(self.cases["allowlisted_service_pass_shape"])

        self.assertEqual("intend", plan["decision"])
        self.assertEqual("planned_non_mutating", plan["status"])
        self.assertEqual("network_exposure_change", plan["required_consent_class"])
        self.assertIn("project_local_config_write", plan["separate_from_consent_classes"])
        self.assertIn("catalog_promotion", plan["separate_from_consent_classes"])
        self.assertIn("user_global_client_trust", plan["separate_from_consent_classes"])
        self.assertIn("token_material_change", plan["separate_from_consent_classes"])
        self.assertEqual("separate_profile_approved", plan["local_state_reference"]["remote_status"])

    def test_denied_tools_have_remote_negative_absence_checks(self) -> None:
        for name in ("broad_serena_scope_changing_exposure_blocked", "denied_admin_token_secret_catalog_tools"):
            with self.subTest(case=name):
                case = self.cases[name]
                plan = self.plan_for(case)
                denied = {item["tool_id"]: item for item in plan["tool_exposure"] if item["decision"] == "deny"}
                checks_by_tool = self.negative_checks_by_tool(plan)

                for tool_id in case["expected"]["denied_tools"]:
                    self.assertIn(tool_id, denied)
                    self.assertIn(tool_id, checks_by_tool)
                    self.assertEqual(
                        {"remote_contextforge_virtual_server", "remote_client"},
                        {check["layer"] for check in checks_by_tool[tool_id]},
                    )
                    self.assertTrue(all(check["expected"] == "absent" for check in checks_by_tool[tool_id]))
                    self.assertTrue(all(check["status"] == "pending" for check in checks_by_tool[tool_id]))

    def test_origin_policy_wildcard_blocks_even_when_reviewed(self) -> None:
        request = self.request_for(
            {
                "overrides": {
                    "reviews": {
                        **self.fixture["default_request"]["reviews"],
                        "origin_policy": {
                            "status": "approved",
                            "reviewed": True,
                            "allowed_origins": ["*"]
                        },
                    }
                }
            }
        )
        plan = self.build_plan(request)

        self.assertEqual("block", plan["decision"])
        self.assertIn("origin_policy_too_broad", self.blockers_by_type(plan))

    def plan_for(self, case: Mapping[str, Any]) -> dict[str, Any]:
        return self.build_plan(self.request_for(case))

    def request_for(self, case: Mapping[str, Any]) -> dict[str, Any]:
        request = copy.deepcopy(self.fixture["default_request"])
        return self.deep_merge(request, case.get("overrides", {}))

    def build_plan(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return remote.build_remote_exposure_plan(
            project_root=self.fixture["project_root"],
            request_id=request["request_id"],
            requested_profile=request.get("requested_profile", remote.DORMANT_REMOTE_PROFILE),
            remote_exposure_requested=bool(request.get("remote_exposure_requested")),
            bind_address=request.get("bind_address"),
            reviews=request.get("reviews"),
            remote_auth_profile=request.get("remote_auth_profile"),
            service_allowlist=request.get("service_allowlist", []),
            excluded_services=request.get("excluded_services", []),
            excluded_tools=request.get("excluded_tools", []),
            candidate_tools=request.get("candidate_tools", []),
            consent_receipt_refs=request.get("consent_receipt_refs", []),
            rollback=request.get("rollback"),
            remote_probe_plan=request.get("remote_probe_plan"),
            diagnostic_redaction=request.get("diagnostic_redaction"),
            generated_at=self.fixture["generated_at"],
        )

    def blockers_by_type(self, plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(blocker["type"]): dict(blocker) for blocker in plan.get("blockers", [])}

    def negative_checks_by_tool(self, plan: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
        checks: dict[str, list[dict[str, Any]]] = {}
        for check in plan.get("negative_exposure_checks", []):
            if check.get("check") == "remote_denied_tool_absent":
                checks.setdefault(str(check["tool_id"]), []).append(dict(check))
        return checks

    def deep_merge(self, base: dict[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
        for key, value in overrides.items():
            if isinstance(value, Mapping) and isinstance(base.get(key), dict):
                base[key] = self.deep_merge(dict(base[key]), value)
            else:
                base[key] = copy.deepcopy(value)
        return base


if __name__ == "__main__":
    unittest.main()
