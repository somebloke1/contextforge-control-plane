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


class SshTmuxSingleServiceLifecycleTests(unittest.TestCase):
    def make_workspace_root(self, prefix: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix=prefix, dir=project_state.WORKSPACE_ROOT)).resolve()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def approve_and_apply(self, root: Path, *, client_type: str) -> dict:
        proposal = helper.propose_project_init(
            project_root=root,
            client_type=client_type,
            selected_services=["ssh-tmux:session_scoped"],
        )
        self.assertEqual([], proposal["skipped_services"])
        selected = proposal["selected_services"][0]
        self.assertEqual("ssh-tmux:session_scoped", selected["service_binding"])
        self.assertEqual("session_scoped", selected["instantiation_class"])
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

    def assert_ssh_tmux_state(self, state: dict, *, client_type: str) -> None:
        self.assertIn("ssh-tmux:session_scoped", state["services"])
        service = state["services"]["ssh-tmux:session_scoped"]
        self.assertEqual("ssh-tmux", service["service_family"])
        self.assertEqual("ssh-tmux:session_scoped", service["service_binding"])
        self.assertEqual("session_scoped", service["instantiation_class"])
        self.assertEqual("server-instances/ssh-tmux", service["backend_instance"])
        self.assertEqual("ssh_tmux_server", service["virtual_server"])
        self.assertEqual("shared_contextforge_service", service["lifecycle"]["activation"])
        self.assertEqual("none", service["provision_status"])
        self.assertEqual("installed", service["verification_layers"]["target_client"]["status"])
        self.assertEqual("safe_default_selected", service["verification_layers"]["tool_policy"]["status"])
        policy = service["verification_layers"]["tool_policy"]["policy"]
        self.assertEqual("read_only", policy["mode"])
        self.assertEqual(["list-sessions", "get-snapshot"], policy["safe_operations"])
        self.assertTrue(policy["requires_mutation_approval"])
        self.assertEqual(
            "opening sessions or sending commands requires explicit approval",
            policy["mutation_boundary"],
        )
        contract = policy["probe_contract"]
        self.assertEqual("list-sessions", contract["default_probe"]["safe_probe_id"])
        self.assertEqual("ssh-tmux-list-sessions", contract["default_probe"]["tool_name_hint"])
        self.assertEqual({}, contract["default_probe"]["arguments"])
        self.assertIn("ssh-tmux-list-sessions", contract["allowed_tool_name_patterns"])
        self.assertIn("ssh-tmux-get-snapshot", contract["allowed_tool_name_patterns"])
        for forbidden in [
            "open session",
            "send command",
            "send keys",
            "close session",
            "remote file read",
            "remote file write",
            "direct shell or tmux command",
            "local process inspection",
        ]:
            self.assertIn(forbidden, contract["forbidden_substitutions"])
        self.assertEqual("installed", service["target_clients"][client_type]["validation_status"])

    def test_ssh_tmux_pi_lifecycle_writes_only_project_state_and_stops_for_reload(self) -> None:
        root = self.make_workspace_root("cf266-pi-test-")
        result = self.approve_and_apply(root, client_type="pi")
        state = project_state.load_state(root)

        self.assertFalse(result["dry_run"])
        self.assertEqual([str(project_state.project_state_path(root))], result["writes"])
        self.assertEqual("pi-project-init-installed", result["next_turn"]["question_id"])
        self.assertEqual("/reload", result["client_reload_requirement"]["command"])
        self.assertFalse((root / "opencode.json").exists())
        self.assertIsNotNone(state)
        assert state is not None
        self.assert_ssh_tmux_state(state, client_type="pi")
        self.assertEqual(
            "shim_activation_planned",
            state["services"]["ssh-tmux:session_scoped"]["target_clients"]["pi"]["status"],
        )

    def test_ssh_tmux_opencode_lifecycle_writes_project_config_state_and_stops_for_new_session(self) -> None:
        root = self.make_workspace_root("cf266-opencode-test-")
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
        self.assertIn("ssh_tmux", opencode_config["mcp"])
        self.assertEqual("local", opencode_config["mcp"]["ssh_tmux"]["type"])
        command = opencode_config["mcp"]["ssh_tmux"]["command"]
        self.assertTrue(any(str(arg).endswith("contextforge_mcp_wrapper.py") for arg in command))
        self.assertIn("ssh_tmux_server", command)
        self.assertIsNotNone(state)
        assert state is not None
        self.assert_ssh_tmux_state(state, client_type="opencode")
        self.assertEqual(
            "project_local_opencode_config_planned",
            state["services"]["ssh-tmux:session_scoped"]["target_clients"]["opencode"]["status"],
        )


if __name__ == "__main__":
    unittest.main()
