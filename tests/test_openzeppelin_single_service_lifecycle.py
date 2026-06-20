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


class OpenZeppelinSingleServiceLifecycleTests(unittest.TestCase):
    def make_workspace_root(self, prefix: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix=prefix, dir=project_state.WORKSPACE_ROOT)).resolve()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def approve_and_apply(self, root: Path, *, client_type: str) -> dict:
        proposal = helper.propose_project_init(
            project_root=root,
            client_type=client_type,
            selected_services=["openzeppelin-solidity-contracts:canonical"],
        )
        self.assertEqual([], proposal["skipped_services"])
        self.assertEqual("openzeppelin-solidity-contracts:canonical", proposal["selected_services"][0]["service_binding"])
        self.assertEqual("shared_canonical", proposal["selected_services"][0]["instantiation_class"])
        self.assertFalse(proposal["selected_services"][0]["bridge"]["needed"])

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

    def assert_openzeppelin_state(self, state: dict, *, client_type: str) -> None:
        self.assertIn("openzeppelin-solidity-contracts:canonical", state["services"])
        service = state["services"]["openzeppelin-solidity-contracts:canonical"]
        self.assertEqual("openzeppelin-solidity-contracts", service["service_family"])
        self.assertEqual("openzeppelin-solidity-contracts:canonical", service["service_binding"])
        self.assertEqual("shared_canonical", service["instantiation_class"])
        self.assertEqual("server-instances/openzeppelin-solidity-contracts", service["backend_instance"])
        self.assertEqual("openzeppelin_solidity_contracts_server", service["virtual_server"])
        self.assertEqual("shared_contextforge_service", service["lifecycle"]["activation"])
        self.assertEqual("none", service["provision_status"])
        self.assertEqual("installed", service["verification_layers"]["target_client"]["status"])
        self.assertEqual("safe_default_selected", service["verification_layers"]["tool_policy"]["status"])
        policy = service["verification_layers"]["tool_policy"]["policy"]
        self.assertEqual("safe_call", policy["mode"])
        self.assertEqual(["solidity-erc20-preview"], policy["safe_operations"])
        contract = policy["probe_contract"]
        self.assertEqual(["openzeppelin-solidity-contracts-solidity-erc20"], contract["allowed_tool_name_patterns"])
        self.assertEqual("solidity-erc20-preview", contract["default_probe"]["safe_probe_id"])
        self.assertEqual("ContextForgePreviewToken", contract["default_probe"]["arguments"]["name"])
        self.assertIn("deployment approval", contract["forbidden_substitutions"])
        self.assertIn("wallet or private key", contract["forbidden_substitutions"])
        self.assertIn("project mutation", contract["forbidden_substitutions"])
        self.assertEqual("installed", service["target_clients"][client_type]["validation_status"])

    def test_openzeppelin_pi_lifecycle_writes_only_project_state_and_stops_for_reload(self) -> None:
        root = self.make_workspace_root("cf264-pi-test-")
        result = self.approve_and_apply(root, client_type="pi")
        state = project_state.load_state(root)

        self.assertFalse(result["dry_run"])
        self.assertEqual([str(project_state.project_state_path(root))], result["writes"])
        self.assertEqual("pi-project-init-installed", result["next_turn"]["question_id"])
        self.assertEqual("/reload", result["client_reload_requirement"]["command"])
        self.assertFalse((root / "opencode.json").exists())
        self.assertIsNotNone(state)
        assert state is not None
        self.assert_openzeppelin_state(state, client_type="pi")
        self.assertEqual(
            "shim_activation_planned",
            state["services"]["openzeppelin-solidity-contracts:canonical"]["target_clients"]["pi"]["status"],
        )

    def test_openzeppelin_opencode_lifecycle_writes_project_config_state_and_stops_for_new_session(self) -> None:
        root = self.make_workspace_root("cf264-opencode-test-")
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
        self.assertIn("openzeppelin_solidity_contracts", opencode_config["mcp"])
        command = opencode_config["mcp"]["openzeppelin_solidity_contracts"]["command"]
        self.assertTrue(any(str(arg).endswith("contextforge_mcp_wrapper.py") for arg in command))
        self.assertIn("openzeppelin_solidity_contracts_server", command)
        self.assertIsNotNone(state)
        assert state is not None
        self.assert_openzeppelin_state(state, client_type="opencode")
        self.assertEqual(
            "project_local_opencode_config_planned",
            state["services"]["openzeppelin-solidity-contracts:canonical"]["target_clients"]["opencode"]["status"],
        )


if __name__ == "__main__":
    unittest.main()
