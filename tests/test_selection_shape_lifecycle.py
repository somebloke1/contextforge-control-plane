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


SINGLE_SELECTION = ["context7:canonical"]
CURATED_SELECTION = [
    "context7:canonical",
    "mentality:static_repo_local",
    "ssh-tmux:session_scoped",
]
ALL_SELECTION = [
    "context7:canonical",
    "exa-search:credential_scoped",
    "github:canonical",
    "mentality:static_repo_local",
    "openzeppelin-solidity-contracts:canonical",
    "playwright:session_scoped",
    "ssh-tmux:session_scoped",
    "web-search:credential_scoped",
    "serena",
]


class SelectionShapeLifecycleTests(unittest.TestCase):
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
            "pre_digest": None,
            "post_digest": common.stable_digest({"instance_slug": identity.instance_slug, "language": language}),
        }

    def approve_and_apply(self, root: Path, *, client_type: str, selected_services: list[str]) -> dict:
        identity = common.project_identity(root)
        includes_serena = "serena" in selected_services or f"serena:{identity.hash}" in selected_services
        proposal = helper.propose_project_init(
            project_root=root,
            client_type=client_type,
            selected_services=selected_services,
            inputs={"language": "python"},
        )
        self.assertEqual([], proposal["skipped_services"])
        self.assertEqual("approve-project-init-plan", proposal["next_turn"]["question_id"])
        if includes_serena:
            self.assertIn("service_provision", proposal["required_consent_classes"])
            self.assertIn("python", list(proposal["required_inputs"].values()))
        else:
            self.assertNotIn("service_provision", proposal["required_consent_classes"])

        selected_bindings = [service["service_binding"] for service in proposal["selected_services"]]
        expected_bindings = [
            f"serena:{identity.hash}" if service == "serena" else service
            for service in selected_services
        ]
        self.assertEqual(expected_bindings, selected_bindings)

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
            return self.fake_provision_result(root, language=language)

        with mock.patch.object(helper, "_run_serena_project_provisioning", side_effect=fake_provision) as provision:
            result = helper.apply_approved_project_init(
                project_root=root,
                plan=proposal,
                receipts=approval["receipts"],
                dry_run=False,
            )

        if includes_serena:
            provision.assert_called_once()
        else:
            provision.assert_not_called()
        result["proposal"] = proposal
        result["approval"] = approval
        result["expected_bindings"] = expected_bindings
        return result

    def assert_state_has_exact_selection(self, root: Path, result: dict, *, client_type: str) -> None:
        state = project_state.load_state(root)
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(set(result["expected_bindings"]), set(state["services"]))
        self.assertEqual(result["expected_bindings"], result["job"]["selected_service_bindings"])
        for binding, service in state["services"].items():
            with self.subTest(binding=binding, client_type=client_type):
                self.assertEqual("installed", service["verification_layers"]["target_client"]["status"])
                self.assertIn(client_type, service["target_clients"])
                self.assertEqual("installed", service["target_clients"][client_type]["validation_status"])

    def test_single_service_selection_applies_for_pi_and_opencode(self) -> None:
        for client_type in ("pi", "opencode"):
            with self.subTest(client_type=client_type):
                root = self.make_workspace_root(f"cf269-single-{client_type}-")
                result = self.approve_and_apply(root, client_type=client_type, selected_services=SINGLE_SELECTION)
                self.assert_state_has_exact_selection(root, result, client_type=client_type)
                if client_type == "pi":
                    self.assertEqual([str(project_state.project_state_path(root))], result["writes"])
                    self.assertEqual("/reload", result["client_reload_requirement"]["command"])
                    self.assertFalse((root / "opencode.json").exists())
                else:
                    self.assertEqual(
                        [str(root / "opencode.json"), str(project_state.project_state_path(root))],
                        result["writes"],
                    )
                    self.assertEqual("start_new_session", result["client_reload_requirement"]["command"])
                    opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
                    self.assertEqual({"context7"}, set(opencode_config["mcp"]))

    def test_curated_multi_service_selection_spans_service_classes_without_omissions(self) -> None:
        expected_classes = {"shared_canonical", "static_repo_local", "session_scoped"}
        for client_type in ("pi", "opencode"):
            with self.subTest(client_type=client_type):
                root = self.make_workspace_root(f"cf269-curated-{client_type}-")
                result = self.approve_and_apply(root, client_type=client_type, selected_services=CURATED_SELECTION)
                classes = {service["instantiation_class"] for service in result["proposal"]["selected_services"]}
                self.assertEqual(expected_classes, classes)
                self.assert_state_has_exact_selection(root, result, client_type=client_type)
                if client_type == "opencode":
                    opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
                    self.assertEqual({"context7", "mentality", "ssh_tmux"}, set(opencode_config["mcp"]))

    def test_all_services_selection_applies_every_readiness_matrix_service(self) -> None:
        expected_service_families = {
            "context7",
            "exa-search",
            "github",
            "mentality",
            "openzeppelin-solidity-contracts",
            "playwright",
            "serena",
            "ssh-tmux",
            "web-search",
        }
        for client_type in ("pi", "opencode"):
            with self.subTest(client_type=client_type):
                root = self.make_workspace_root(f"cf269-all-{client_type}-")
                result = self.approve_and_apply(root, client_type=client_type, selected_services=ALL_SELECTION)
                self.assertEqual(9, len(result["proposal"]["selected_services"]))
                self.assertEqual(
                    expected_service_families,
                    {service["service_family"] for service in result["proposal"]["selected_services"]},
                )
                self.assert_state_has_exact_selection(root, result, client_type=client_type)
                state = project_state.load_state(root)
                assert state is not None
                self.assertEqual(
                    expected_service_families,
                    {service["service_family"] for service in state["services"].values()},
                )
                step_types = [step["operation_type"] for step in result["job"]["step_statuses"]]
                self.assertIn("provision_project_scoped_serena", step_types)
                if client_type == "opencode":
                    self.assertLess(
                        step_types.index("provision_project_scoped_serena"),
                        step_types.index("write_opencode_project_config"),
                    )
                    opencode_config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
                    self.assertEqual(
                        {
                            "context7",
                            "exa_search",
                            "github",
                            "mentality",
                            "openzeppelin_solidity_contracts",
                            "playwright",
                            "serena",
                            "ssh_tmux",
                            "web_search",
                        },
                        set(opencode_config["mcp"]),
                    )
                else:
                    self.assertLess(
                        step_types.index("provision_project_scoped_serena"),
                        step_types.index("record_pi_shim_activation_metadata"),
                    )


if __name__ == "__main__":
    unittest.main()
