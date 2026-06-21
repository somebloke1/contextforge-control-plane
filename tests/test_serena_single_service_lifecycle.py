import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import control_plane_project_init_helper as helper  # noqa: E402
import control_plane_project_state as project_state  # noqa: E402
import project_init_common as common  # noqa: E402


class SerenaSingleServiceLifecycleTests(unittest.TestCase):
    def make_workspace_root(self, prefix: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix=prefix, dir=project_state.WORKSPACE_ROOT)).resolve()
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def fake_provision_result(self, root: Path, *, language: str) -> dict:
        identity = common.project_identity(root)
        return {
            "service_binding": f"serena:{identity.hash}",
            "status": "completed",
            "operation_type": "provision_project_scoped_serena",
            "language": language,
            "instance_slug": identity.instance_slug,
            "server_name": identity.server_name,
            "manifest_path": f"server-instances/{identity.instance_slug}/instance.json",
            "contextforge_server_id": "vs-test",
            "pre_digest": None,
            "post_digest": common.stable_digest({"instance_slug": identity.instance_slug, "language": language}),
        }

    def approve_and_apply(self, root: Path, *, client_type: str, language: str = "python") -> dict:
        identity = common.project_identity(root)
        proposal = helper.propose_project_init(
            project_root=root,
            client_type=client_type,
            selected_services=["serena"],
            inputs={f"serena:{identity.hash}": {"language": language}},
        )
        self.assertNotEqual("needs_input", proposal.get("status"))
        self.assertEqual([], proposal["skipped_services"])
        self.assertEqual({"language": language}, proposal["required_inputs"][f"serena:{identity.hash}"])
        self.assertIn("service_provision", proposal["required_consent_classes"])
        selected = proposal["selected_services"][0]
        self.assertEqual(f"serena:{identity.hash}", selected["service_binding"])
        self.assertEqual("instance_per_project", selected["instantiation_class"])
        self.assertEqual("client_local_project_scoped", selected["activation_class"])
        self.assertEqual("project-scoped provisioning", selected["scope_label"])
        self.assertEqual("required", selected["provisioning"]["status"])
        self.assertEqual(str(root), selected["scope"]["workspace_root"])

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

        def fake_provision(provision_root: Path, service: dict, *, language: str, client_type: str) -> dict:
            self.assertEqual(root, provision_root)
            self.assertEqual(f"serena:{identity.hash}", service["service_binding"])
            self.assertEqual(client_type, proposal["client_type"])
            return self.fake_provision_result(root, language=language)

        with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision) as provision:
            result = helper.apply_approved_project_init(
                project_root=root,
                plan=proposal,
                receipts=approval["receipts"],
                dry_run=False,
            )

        provision.assert_called_once()
        self.assertEqual(language, provision.call_args.kwargs["language"])
        result["proposal"] = proposal
        result["approval"] = approval
        return result

    def assert_serena_state(self, state: dict, *, root: Path, client_type: str) -> None:
        identity = common.project_identity(root)
        binding = f"serena:{identity.hash}"
        self.assertIn(binding, state["services"])
        service = state["services"][binding]
        self.assertEqual("serena", service["service_family"])
        self.assertEqual(binding, service["service_binding"])
        self.assertEqual("instance_per_project", service["instantiation_class"])
        self.assertEqual(f"server-instances/{identity.instance_slug}", service["backend_instance"])
        self.assertEqual(identity.server_name, service["virtual_server"])
        self.assertEqual("project_scoped_service_provision", service["lifecycle"]["activation"])
        self.assertEqual("created", service["provision_status"])
        self.assertEqual("provisioned_pending_readback", service["lifecycle"]["contextforge_readback_status"])
        self.assertEqual("provisioned_pending_readback", service["verification_layers"]["contextforge_gateway"]["status"])
        self.assertEqual("installed", service["verification_layers"]["target_client"]["status"])
        self.assertEqual("safe_default_selected", service["verification_layers"]["tool_policy"]["status"])
        policy = service["verification_layers"]["tool_policy"]["policy"]
        self.assertEqual("skip_without_service_policy", policy["mode"])
        self.assertEqual([], policy["safe_operations"])
        self.assertEqual("installed", service["target_clients"][client_type]["validation_status"])
        self.assertNotIn("x_contextforge_server_id", service)

    def assert_provision_step_precedes_client_write(self, result: dict, *, client_operation: str) -> None:
        step_types = [step["operation_type"] for step in result["job"]["step_statuses"]]
        self.assertIn("provision_project_scoped_serena", step_types)
        self.assertIn(client_operation, step_types)
        self.assertLess(step_types.index("provision_project_scoped_serena"), step_types.index(client_operation))

    def test_serena_selection_stops_for_language_before_approval(self) -> None:
        root = self.make_workspace_root("cf268-input-test-")
        identity = common.project_identity(root)
        proposal = helper.propose_project_init(
            project_root=root,
            client_type="pi",
            selected_services=[f"serena:{identity.hash}"],
        )

        self.assertEqual("needs_input", proposal["status"])
        self.assertEqual("language", proposal["required_input"])
        self.assertEqual(f"serena:{identity.hash}", proposal["service_binding"])
        self.assertTrue(proposal["next_turn"]["must_stop"])
        self.assertNotIn("approval_challenge", proposal)
        self.assertIn("python", {choice["id"] for choice in proposal["next_turn"]["choices"]})
        self.assertIn("defer", {choice["id"] for choice in proposal["next_turn"]["choices"]})

    def test_serena_pi_lifecycle_provisions_then_writes_only_project_state(self) -> None:
        root = self.make_workspace_root("cf268-pi-test-")
        result = self.approve_and_apply(root, client_type="pi", language="python")
        state = project_state.load_state(root)

        self.assertFalse(result["dry_run"])
        self.assertEqual([str(project_state.project_state_path(root))], result["writes"])
        self.assertEqual("pi-project-init-installed", result["next_turn"]["question_id"])
        self.assertEqual("/reload", result["client_reload_requirement"]["command"])
        self.assertFalse((root / "opencode.json").exists())
        self.assertIsNotNone(state)
        assert state is not None
        self.assert_serena_state(state, root=root, client_type="pi")
        self.assertEqual(
            "shim_activation_planned",
            state["services"][f"serena:{common.project_identity(root).hash}"]["target_clients"]["pi"]["status"],
        )
        self.assert_provision_step_precedes_client_write(result, client_operation="record_pi_shim_activation_metadata")

    def test_serena_opencode_lifecycle_provisions_then_writes_project_config_state(self) -> None:
        root = self.make_workspace_root("cf268-opencode-test-")
        result = self.approve_and_apply(root, client_type="opencode", language="python")
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
        self.assertIn("serena", opencode_config["mcp"])
        self.assertEqual("local", opencode_config["mcp"]["serena"]["type"])
        command = opencode_config["mcp"]["serena"]["command"]
        self.assertTrue(any(str(arg).endswith("contextforge_mcp_wrapper.py") for arg in command))
        self.assertIn(common.project_identity(root).server_name, command)
        self.assertIsNotNone(state)
        assert state is not None
        self.assert_serena_state(state, root=root, client_type="opencode")
        self.assertEqual(
            "project_local_opencode_config_planned",
            state["services"][f"serena:{common.project_identity(root).hash}"]["target_clients"]["opencode"]["status"],
        )
        self.assert_provision_step_precedes_client_write(result, client_operation="write_opencode_project_config")


if __name__ == "__main__":
    unittest.main()
