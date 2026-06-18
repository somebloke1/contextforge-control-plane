from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_service_onboarding_helper as helper


FIXTURE = REPO_ROOT / "tests/fixtures/control_plane_service_onboarding_cases.json"
PROJECT_ROOT = "/home/dgk/workspace/cf-controlplane"


def cases_by_name() -> dict[str, dict[str, object]]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {case["name"]: case for case in data["cases"]}


class ControlPlaneServiceOnboardingHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = cases_by_name()

    def record(self, case_name: str) -> dict[str, object]:
        descriptor = self.cases[case_name]["descriptor"]
        return helper.build_onboarding_record(descriptor, project_root=PROJECT_ROOT, issue="#52")  # type: ignore[arg-type]

    def test_project_scoped_stdio_service_stops_at_docker_approval_gate(self) -> None:
        record = self.record("serena_project_scoped_stdio_dev_docker_gate")

        self.assertEqual("approval_required", record["status"])
        self.assertFalse(record["mutation_allowed"])
        self.assertEqual("approval_gate", record["current_state"])
        self.assertEqual("serena", record["candidate_service"])
        self.assertEqual("Project-scoped backend", record["integration_strategy"]["primary_paradigm"])  # type: ignore[index]
        self.assertIn("Package-provided bridge/transceiver", record["integration_strategy"]["secondary_validation_paradigms"])  # type: ignore[index]
        self.assertIn("Dev Docker sidecar", record["integration_strategy"]["secondary_validation_paradigms"])  # type: ignore[index]
        self.assertIn("docker_dev_surface", record["approval_gate"]["required_approval_types"])  # type: ignore[index]
        self.assertIn(
            "Approve Docker development-surface execution for this service only",
            record["approval_gate"]["exact_approval_text"][0],  # type: ignore[index]
        )
        self.assertIn("do not start, stop, build, or rebuild Docker containers", record["non_actions"])

    def test_native_source_only_service_is_ready_for_handoff(self) -> None:
        record = self.record("native_http_shared_docs_source_only")

        self.assertEqual("ready_for_handoff", record["status"])
        self.assertEqual("handoff", record["current_state"])
        self.assertFalse(record["approval_gate"]["approval_required"])  # type: ignore[index]
        self.assertEqual("Direct native registration", record["integration_strategy"]["primary_paradigm"])  # type: ignore[index]
        self.assertEqual("docs-search", record["footprint_plan"]["service_slug"])  # type: ignore[index]
        self.assertIn("open or update a focused issue/PR", " ".join(record["next_issue_pr_steps"]))  # type: ignore[index]

    def test_shared_stdio_bridge_service_stops_at_dev_docker_approval_gate(self) -> None:
        record = self.record("shared_stdio_bridge_dev_docker_gate")

        self.assertEqual("approval_required", record["status"])
        self.assertEqual("approval_gate", record["current_state"])
        self.assertEqual("Package-provided bridge/transceiver", record["integration_strategy"]["primary_paradigm"])  # type: ignore[index]
        self.assertIn("Dev Docker sidecar", record["integration_strategy"]["secondary_validation_paradigms"])  # type: ignore[index]
        self.assertIn("docker_dev_surface", record["approval_gate"]["required_approval_types"])  # type: ignore[index]
        self.assertIn(
            "Which stock bridge/transceiver command exposes the missing HTTP/SSE transport?",
            record["next_questions"],
        )
        self.assertIn(
            "Direct native registration rejected until packetized HTTP/SSE endpoint evidence exists",
            record["integration_strategy"]["rejected_alternatives"],  # type: ignore[index]
        )

    def test_credential_scoped_service_records_scope_question_and_registry_gate(self) -> None:
        record = self.record("github_credential_scoped_registry_gate")

        self.assertEqual("approval_required", record["status"])
        self.assertEqual("Credential-scoped backend", record["integration_strategy"]["primary_paradigm"])  # type: ignore[index]
        self.assertIn("contextforge_dev_registry", record["approval_gate"]["required_approval_types"])  # type: ignore[index]
        self.assertIn(
            "Which credential, account, tenant, token, or installation boundary defines this service binding?",
            record["next_questions"],
        )
        self.assertIn(
            "Which exact approval packet should unlock the next runtime or client surface?",
            record["next_questions"],
        )
        self.assertIn(
            "credential scope must be proven by metadata and negative readback before broader client exposure",
            record["residual_risks"],
        )

    def test_client_session_local_stdio_service_keeps_source_only_handoff(self) -> None:
        record = self.record("ssh_tmux_client_session_local_bridge")

        self.assertEqual("ready_for_handoff", record["status"])
        self.assertEqual("handoff", record["current_state"])
        self.assertFalse(record["approval_gate"]["approval_required"])  # type: ignore[index]
        self.assertEqual("Client-local or session-scoped backend", record["integration_strategy"]["primary_paradigm"])  # type: ignore[index]
        self.assertIn("Package-provided bridge/transceiver", record["integration_strategy"]["secondary_validation_paradigms"])  # type: ignore[index]
        self.assertIn(
            "Which client-local state, live session, caller identity, or process authority defines this service binding?",
            record["next_questions"],
        )
        self.assertIn(
            "Which stock bridge/transceiver command exposes the missing HTTP/SSE transport?",
            record["next_questions"],
        )
        self.assertIn("Pi client Docker", record["footprint_plan"]["client_surfaces"])  # type: ignore[index]
        self.assertIn("do not write global or client config", record["non_actions"])

    def test_missing_source_and_classification_evidence_emits_stable_questions_and_redacts(self) -> None:
        first = self.record("missing_evidence_prompts_questions")
        second = self.record("missing_evidence_prompts_questions")

        self.assertEqual(first, second)
        self.assertEqual("needs_user_input", first["status"])
        self.assertEqual("source_discovery", first["current_state"])
        self.assertIn(
            "What upstream docs, package names, commands, local paths, or issue links prove the service shape?",
            first["next_questions"],
        )
        self.assertEqual("<redacted>", first["source_descriptor"]["api_key"])  # type: ignore[index]
        self.assertIn("source_evidence", {blocker["field"] for blocker in first["blockers"]})  # type: ignore[index]
        self.assertIn("plan_type", {blocker["field"] for blocker in _blockers(first)})

    def test_previous_record_resume_merges_new_evidence_without_writing_state(self) -> None:
        previous = self.record("missing_evidence_prompts_questions")
        resumed = helper.build_onboarding_record(
            {
                "source_evidence": [{"type": "upstream_doc", "ref": "https://example.invalid/unknown-service"}],
                "classification": {
                    "plan_type": "source_only_scaffolding",
                    "localization_type": "shared_canonical",
                    "functional_type": "search_retrieval",
                    "transport_type": "streamable_http",
                    "state_type": "stateless",
                    "approval_type": "source_only",
                },
            },
            project_root=PROJECT_ROOT,
            issue="#52",
            previous_record=previous,
            session_id="svc-onboarding-unknown-service",
        )

        self.assertEqual("ready_for_handoff", resumed["status"])
        self.assertEqual("handoff", resumed["current_state"])
        self.assertEqual("unknown-service", resumed["candidate_service"])
        self.assertFalse(resumed["mutation_allowed"])
        self.assertEqual("stdout_only", resumed["dialogue_session"]["storage_mode"])  # type: ignore[index]
        self.assertFalse(resumed["dialogue_session"]["write_persistence"])  # type: ignore[index]
        self.assertEqual("previous_record", resumed["dialogue_session"]["resume_source"])  # type: ignore[index]
        self.assertEqual("source_discovery", resumed["dialogue_session"]["previous_state"])  # type: ignore[index]
        self.assertEqual(2, resumed["dialogue_session"]["turn_index"])  # type: ignore[index]
        self.assertEqual(["source_discovery", "handoff"], resumed["dialogue_session"]["state_history"])  # type: ignore[index]
        self.assertIn(
            "What upstream docs, package names, commands, local paths, or issue links prove the service shape?",
            resumed["dialogue_session"]["answered_questions"],  # type: ignore[index]
        )
        self.assertEqual("svc-onboarding-unknown-service", resumed["dialogue_session"]["session_id"])  # type: ignore[index]
        self.assertEqual(
            {"from_state": "source_discovery", "from_status": "needs_user_input", "to_state": "handoff", "status": "ready_for_handoff"},
            resumed["dialogue_session"]["history"][-1],  # type: ignore[index]
        )
        self.assertEqual("Direct native registration", resumed["dialogue_session"]["decision_log"][-1]["primary_paradigm"])  # type: ignore[index]
        self.assertFalse(resumed["dialogue_session"]["decision_log"][-1]["mutation_allowed"])  # type: ignore[index]
        self.assertIn(
            {"type": "upstream_doc", "ref": "https://example.invalid/unknown-service"},
            resumed["source_evidence"],
        )

    def test_output_is_json_compatible_and_no_mutation_recorded(self) -> None:
        record = self.record("serena_project_scoped_stdio_dev_docker_gate")

        encoded = json.dumps(record, sort_keys=True)
        self.assertIn('"mutation_allowed": false', encoded)
        for forbidden in [
            "do not register ContextForge services",
            "do not mutate systemd units or processes",
            "do not write global or client config",
            "do not mutate the legacy archive checkout",
        ]:
            self.assertIn(forbidden, record["non_actions"])

    def test_cli_emits_clean_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                "--descriptor",
                str(FIXTURE),
                "--case",
                "missing_evidence_prompts_questions",
                "--project-root",
                PROJECT_ROOT,
                "--issue",
                "#52",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual("", result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual("needs_user_input", output["status"])
        self.assertEqual("source_discovery", output["current_state"])

    def test_cli_resumes_from_previous_record(self) -> None:
        previous = self.record("missing_evidence_prompts_questions")
        descriptor = {
            "classification": {
                "plan_type": "source_only_scaffolding",
                "localization_type": "shared_canonical",
                "functional_type": "search_retrieval",
                "transport_type": "streamable_http",
                "state_type": "stateless",
                "approval_type": "source_only",
            },
            "source_evidence": [{"type": "package", "ref": "unknown-service"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            previous_path = Path(tmp) / "previous.json"
            descriptor_path = Path(tmp) / "descriptor.json"
            previous_path.write_text(json.dumps(previous), encoding="utf-8")
            descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--descriptor",
                    str(descriptor_path),
                    "--previous-record",
                    str(previous_path),
                    "--session-id",
                    "svc-onboarding-cli",
                    "--project-root",
                    PROJECT_ROOT,
                    "--issue",
                    "#52",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        self.assertEqual("", result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual("ready_for_handoff", output["status"])
        self.assertEqual("previous_record", output["dialogue_session"]["resume_source"])
        self.assertEqual("svc-onboarding-cli", output["dialogue_session"]["session_id"])
        self.assertEqual(2, output["dialogue_session"]["turn_index"])
        self.assertEqual(["source_discovery", "handoff"], output["dialogue_session"]["state_history"])

    def test_descriptor_must_be_mapping(self) -> None:
        with self.assertRaises(helper.ServiceOnboardingInputError):
            helper.build_onboarding_record(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_previous_record_must_include_source_descriptor_for_resume(self) -> None:
        with self.assertRaises(helper.ServiceOnboardingInputError):
            helper.build_onboarding_record({}, previous_record={"status": "needs_user_input"})


def _blockers(record: dict[str, object]) -> list[dict[str, str]]:
    questions = set(record["next_questions"])  # type: ignore[arg-type]
    return [
        {"field": field, "question": entry["next_evidence_step"] or ""}
        for field, entry in record["classification"].items()  # type: ignore[union-attr]
        if entry["status"] != "known" and entry["next_evidence_step"] in questions
    ]


if __name__ == "__main__":
    unittest.main()
