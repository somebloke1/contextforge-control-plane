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


class Context7SingleServiceLifecycleTests(unittest.TestCase):
    def make_workspace_root(self, prefix: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix=prefix, dir=project_state.WORKSPACE_ROOT)).resolve()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def approve_and_apply(self, root: Path, *, client_type: str) -> dict:
        proposal = helper.propose_project_init(
            project_root=root,
            client_type=client_type,
            selected_services=["context7:canonical"],
        )
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

    def test_context7_pi_lifecycle_writes_only_project_state_and_stops_for_reload(self) -> None:
        root = self.make_workspace_root("cf260-pi-test-")
        result = self.approve_and_apply(root, client_type="pi")
        state = project_state.load_state(root)

        self.assertFalse(result["dry_run"])
        self.assertEqual([str(project_state.project_state_path(root))], result["writes"])
        self.assertEqual("pi-project-init-installed", result["next_turn"]["question_id"])
        self.assertEqual("/reload", result["client_reload_requirement"]["command"])
        self.assertFalse((root / "opencode.json").exists())
        self.assertIsNotNone(state)
        assert state is not None
        self.assertIn("context7:canonical", state["services"])
        self.assertEqual(
            "shared_contextforge_service",
            state["services"]["context7:canonical"]["lifecycle"]["activation"],
        )
        self.assertEqual(
            "installed",
            state["services"]["context7:canonical"]["verification_layers"]["target_client"]["status"],
        )

    def test_context7_opencode_lifecycle_writes_project_config_state_and_stops_for_new_session(self) -> None:
        root = self.make_workspace_root("cf260-opencode-test-")
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
        self.assertIn("context7", opencode_config["mcp"])
        self.assertIsNotNone(state)
        assert state is not None
        self.assertIn("context7:canonical", state["services"])
        service = state["services"]["context7:canonical"]
        self.assertEqual("shared_contextforge_service", service["lifecycle"]["activation"])
        self.assertEqual(
            "project_local_opencode_config_planned",
            service["target_clients"]["opencode"]["status"],
        )
        self.assertEqual(
            "installed",
            service["verification_layers"]["target_client"]["status"],
        )


if __name__ == "__main__":
    unittest.main()
