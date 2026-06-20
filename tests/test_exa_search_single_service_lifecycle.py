import json
import shutil
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import control_plane_project_init_helper as helper  # noqa: E402
import control_plane_project_state as project_state  # noqa: E402


class ExaSearchSingleServiceLifecycleTests(unittest.TestCase):
    def make_workspace_root(self, prefix: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix=prefix, dir=project_state.WORKSPACE_ROOT)).resolve()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def approve_and_apply(self, root: Path, *, client_type: str) -> dict:
        proposal = helper.propose_project_init(
            project_root=root,
            client_type=client_type,
            selected_services=["exa-search:credential_scoped"],
        )
        self.assertEqual([], proposal["skipped_services"])
        selected = proposal["selected_services"][0]
        self.assertEqual("exa-search:credential_scoped", selected["service_binding"])
        self.assertEqual("credential_scoped", selected["instantiation_class"])
        self.assertTrue(selected["bridge"]["needed"])

        local_event = helper.record_local_approval_event(
            project_root=root,
            plan=proposal,
            issuer_token=helper._LOCAL_APPROVAL_ISSUER_TOKEN,
            channel="interactive_user",
        )
        approval = helper.approve_project_init_plan(
            project_root=root,
            plan=proposal,
            approval={
                "decision": "approve",
                "challenge_id": proposal["approval_challenge"]["challenge_id"],
                "plan_digest": proposal["plan_digest"],
            },
            local_approval_event_ref=local_event["event_ref"],
            actor="developer",
            source_client=client_type,
            source_client_auth_strength="shared_token",
        )
        self.assertEqual("allow", approval["decision"])
        result = helper.apply_approved_project_init(
            project_root=root,
            plan=proposal,
            receipts=approval["receipts"],
            dry_run=False,
        )
        result["proposal"] = proposal
        result["approval"] = approval
        return result

    def assert_exa_search_state(self, state: dict, *, client_type: str) -> None:
        self.assertIn("exa-search:credential_scoped", state["services"])
        service = state["services"]["exa-search:credential_scoped"]
        self.assertEqual("exa-search", service["service_family"])
        self.assertEqual("exa-search:credential_scoped", service["service_binding"])
        self.assertEqual("credential_scoped", service["instantiation_class"])
        self.assertEqual("server-instances/exa-search", service["backend_instance"])
        self.assertEqual("exa_search_server", service["virtual_server"])
        self.assertEqual("shared_contextforge_service", service["lifecycle"]["activation"])
        self.assertEqual("none", service["provision_status"])
        self.assertEqual("installed", service["verification_layers"]["target_client"]["status"])
        self.assertEqual("safe_default_selected", service["verification_layers"]["tool_policy"]["status"])
        policy = service["verification_layers"]["tool_policy"]["policy"]
        self.assertEqual("safe_call", policy["mode"])
        self.assertEqual(["web-search-exa", "web-fetch-exa"], policy["safe_operations"])
        self.assertFalse(policy["requires_mutation_approval"])
        self.assertEqual("installed", service["target_clients"][client_type]["validation_status"])

    def test_exa_search_pi_lifecycle_writes_only_project_state_and_stops_for_reload(self) -> None:
        root = self.make_workspace_root("cf261-pi-test-")
        result = self.approve_and_apply(root, client_type="pi")
        state = project_state.load_state(root)

        self.assertFalse(result["dry_run"])
        self.assertEqual([str(project_state.project_state_path(root))], result["writes"])
        self.assertEqual("pi-project-init-installed", result["next_turn"]["question_id"])
        self.assertEqual("/reload", result["client_reload_requirement"]["command"])
        self.assertFalse((root / "opencode.json").exists())
        self.assertIsNotNone(state)
        assert state is not None
        self.assert_exa_search_state(state, client_type="pi")
        self.assertEqual(
            "shim_activation_planned",
            state["services"]["exa-search:credential_scoped"]["target_clients"]["pi"]["status"],
        )

    def test_exa_search_opencode_lifecycle_writes_project_config_state_and_stops_for_new_session(self) -> None:
        root = self.make_workspace_root("cf261-opencode-test-")
        result = self.approve_and_apply(root, client_type="opencode")
        state = project_state.load_state(root)
        opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))

        self.assertFalse(result["dry_run"])
        self.assertEqual(
            [
                str(root / "opencode.json"),
                str(project_state.project_state_path(root)),
            ],
            result["writes"],
        )
        self.assertEqual("opencode-project-init-installed", result["next_turn"]["question_id"])
        self.assertEqual("start_new_session", result["client_reload_requirement"]["command"])
        self.assertIn("exa_search", opencode_config["mcp"])
        self.assertEqual("local", opencode_config["mcp"]["exa_search"]["type"])
        command = opencode_config["mcp"]["exa_search"]["command"]
        self.assertTrue(any(str(arg).endswith("contextforge_mcp_wrapper.py") for arg in command))
        self.assertIn("exa_search_server", command)
        serialized = json.dumps(opencode_config)
        self.assertNotIn("EXA_API_KEY", serialized)
        self.assertNotIn("GEMINI_API_KEY", serialized)
        self.assertIsNotNone(state)
        assert state is not None
        self.assert_exa_search_state(state, client_type="opencode")
        self.assertEqual(
            "project_local_opencode_config_planned",
            state["services"]["exa-search:credential_scoped"]["target_clients"]["opencode"]["status"],
        )


if __name__ == "__main__":
    unittest.main()
