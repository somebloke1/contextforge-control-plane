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

    def test_serena_source_only_project_scoped_record_keeps_provisioning_abeyant(self) -> None:
        record = self.record("serena_source_only_project_scoped_abeyant_provisioning")

        self.assertEqual("ready_for_handoff", record["status"])
        self.assertEqual("handoff", record["current_state"])
        self.assertEqual("serena", record["candidate_service"])
        self.assertFalse(record["approval_gate"]["approval_required"])  # type: ignore[index]
        self.assertEqual("source_only_scaffolding", record["classification"]["plan_type"]["value"])  # type: ignore[index]
        self.assertEqual("project_scoped", record["classification"]["localization_type"]["value"])  # type: ignore[index]
        self.assertEqual("Project-scoped backend", record["integration_strategy"]["primary_paradigm"])  # type: ignore[index]
        self.assertEqual("serena-cf-controlplane-d46fe58a2a20", record["footprint_plan"]["service_slug"])  # type: ignore[index]
        self.assertEqual("deferred", record["feasibility"]["verdict"])  # type: ignore[index]
        self.assertIn("abeyant", " ".join(record["feasibility"]["notes"]))  # type: ignore[index]
        self.assertIn("hard-requires the project-scoped backend", " ".join(record["residual_risks"]))  # type: ignore[index]
        self.assertIn(
            "What project-local state does the backend read or write, and how will it be isolated?",
            record["next_questions"],
        )
        gate = record["pre_runtime_workflow_gate"]
        self.assertEqual("ready_for_pre_runtime_handoff", gate["gate_status"])  # type: ignore[index]
        self.assertEqual([], gate["missing_dimensions"])  # type: ignore[index]
        self.assertIn("serena_project_backend_provisioning_readback", _probe_layers(gate))  # type: ignore[arg-type]
        provisioning_readback = _probe_layer(gate, "serena_project_backend_provisioning_readback")
        self.assertTrue(provisioning_readback["required_before_runtime"])
        self.assertFalse(provisioning_readback["runtime_execution"])

    def test_native_source_only_service_is_ready_for_handoff(self) -> None:
        record = self.record("native_http_shared_docs_source_only")

        self.assertEqual("ready_for_handoff", record["status"])
        self.assertEqual("handoff", record["current_state"])
        self.assertFalse(record["approval_gate"]["approval_required"])  # type: ignore[index]
        spec = record["guidance_plan"]["abstract_service_spec"]  # type: ignore[index]
        self.assertEqual("known", spec["status"])  # type: ignore[index]
        self.assertEqual("contextforge://service-specs/docs-search/abstract/v1", spec["resource_uri"])  # type: ignore[index]
        self.assertIn("shared documentation lookup", spec["summary"])  # type: ignore[index]
        self.assertIn("register a ContextForge resource", record["guidance_plan"]["publication_requirement"])  # type: ignore[index]
        self.assertEqual("Direct native registration", record["integration_strategy"]["primary_paradigm"])  # type: ignore[index]
        self.assertEqual("docs-search", record["footprint_plan"]["service_slug"])  # type: ignore[index]
        self.assertIn("open or update a focused issue/PR", " ".join(record["next_issue_pr_steps"]))  # type: ignore[index]
        gate = record["pre_runtime_workflow_gate"]
        self.assertFalse(gate["runtime_work_allowed"])  # type: ignore[index]
        self.assertEqual("ready_for_pre_runtime_handoff", gate["gate_status"])  # type: ignore[index]
        self.assertEqual([], gate["missing_dimensions"])  # type: ignore[index]
        self.assertIn("source_evidence", gate["known_dimensions"])  # type: ignore[index]
        self.assertIn("transport", gate["known_dimensions"])  # type: ignore[index]
        self.assertEqual(["native_transport_contract_readback"], _probe_layers(gate))  # type: ignore[arg-type]

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
        gate = record["pre_runtime_workflow_gate"]
        self.assertFalse(gate["runtime_work_allowed"])  # type: ignore[index]
        self.assertEqual("approval_required_before_runtime", gate["gate_status"])  # type: ignore[index]
        self.assertEqual([], gate["missing_dimensions"])  # type: ignore[index]
        self.assertIn("bridge_transport_smoke_plan", _probe_layers(gate))  # type: ignore[arg-type]
        self.assertIn("approval_scoped_runtime_readback", _probe_layers(gate))  # type: ignore[arg-type]

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
        gate = record["pre_runtime_workflow_gate"]
        self.assertFalse(gate["runtime_work_allowed"])  # type: ignore[index]
        self.assertEqual("approval_required_before_runtime", gate["gate_status"])  # type: ignore[index]
        self.assertEqual([], gate["missing_dimensions"])  # type: ignore[index]
        self.assertIn("credential_boundary", gate["known_dimensions"])  # type: ignore[index]
        self.assertIn("credential_scope_negative_readback", _probe_layers(gate))  # type: ignore[arg-type]

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
        gate = record["pre_runtime_workflow_gate"]
        self.assertEqual("ready_for_pre_runtime_handoff", gate["gate_status"])  # type: ignore[index]
        self.assertEqual([], gate["missing_dimensions"])  # type: ignore[index]
        self.assertIn("bridge_transport_smoke_plan", _probe_layers(gate))  # type: ignore[arg-type]
        self.assertIn("client_session_scope_probe", _probe_layers(gate))  # type: ignore[arg-type]

    def test_openzeppelin_real_service_fixture_is_source_only_handoff(self) -> None:
        record = self.record("openzeppelin_remote_native_hosted_source_only")

        self.assertEqual("ready_for_handoff", record["status"])
        self.assertEqual("handoff", record["current_state"])
        self.assertEqual("openzeppelin-solidity-contracts", record["candidate_service"])
        self.assertFalse(record["mutation_allowed"])
        self.assertFalse(record["approval_gate"]["approval_required"])  # type: ignore[index]
        self.assertEqual("Direct native registration", record["integration_strategy"]["primary_paradigm"])  # type: ignore[index]
        self.assertEqual("remote_native_hosted", record["classification"]["localization_type"]["value"])  # type: ignore[index]
        self.assertEqual("remote_api_tool", record["classification"]["functional_type"]["value"])  # type: ignore[index]
        self.assertEqual("streamable_http", record["classification"]["transport_type"]["value"])  # type: ignore[index]
        self.assertEqual("stateless", record["classification"]["state_type"]["value"])  # type: ignore[index]
        self.assertEqual("source_only", record["classification"]["approval_type"]["value"])  # type: ignore[index]
        self.assertIn(
            {"type": "local_path", "ref": "server-instances/openzeppelin-solidity-contracts/instance.json"},
            record["source_evidence"],
        )
        self.assertIn("docs/safe-client-visible-validation-probes.md", record["footprint_plan"]["docs"])  # type: ignore[index]
        self.assertIn(
            "runtime/client validation is unproven until the exact target client lists and calls the ContextForge-visible OpenZeppelin probe",
            record["residual_risks"],
        )
        self.assertIn(
            "generated Solidity is not audited or deployable from this source-only onboarding record",
            record["residual_risks"],
        )
        self.assertIn(
            "registry state is unproven until a separately approved ContextForge dev registry readback exists",
            record["residual_risks"],
        )
        gate = record["pre_runtime_workflow_gate"]
        self.assertFalse(gate["runtime_work_allowed"])  # type: ignore[index]
        self.assertEqual("ready_for_pre_runtime_handoff", gate["gate_status"])  # type: ignore[index]
        self.assertEqual([], gate["missing_dimensions"])  # type: ignore[index]
        self.assertIn("canonical_service_identity", gate["known_dimensions"])  # type: ignore[index]
        self.assertEqual(["native_transport_contract_readback"], _probe_layers(gate))  # type: ignore[arg-type]

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
        spec = first["guidance_plan"]["abstract_service_spec"]  # type: ignore[index]
        self.assertEqual("draft_generated", spec["status"])  # type: ignore[index]
        self.assertTrue(spec["review_required"])  # type: ignore[index]
        self.assertEqual("contextforge://service-specs/unknown-service/abstract/v1", spec["resource_uri"])  # type: ignore[index]
        self.assertIn("publication_requirement", first["guidance_plan"])  # type: ignore[operator]
        gate = first["pre_runtime_workflow_gate"]
        self.assertFalse(gate["runtime_work_allowed"])  # type: ignore[index]
        self.assertEqual("blocked", gate["gate_status"])  # type: ignore[index]
        for dimension in [
            "source_evidence",
            "scope_locality",
            "transport",
            "state_footprint",
            "approval_boundary",
            "validation_probe_plan",
        ]:
            self.assertIn(dimension, gate["missing_dimensions"])  # type: ignore[index]
            self.assertIn(f"pre_runtime_workflow_gate.{dimension}", {blocker["field"] for blocker in gate["blockers"]})  # type: ignore[index]
        self.assertIn(
            "Which validation probe layers should be planned from source evidence without running them?",
            first["next_questions"],
        )

    def test_source_lead_without_evidence_routes_to_read_only_research_plan(self) -> None:
        record = helper.build_onboarding_record(
            {
                "candidate_service": "possible-docs-service",
                "operator_goal": "Investigate whether this lead can become a ContextForge service.",
                "source_leads": ["possible-docs-mcp package"],
            },
            project_root=PROJECT_ROOT,
            issue="#52",
        )

        self.assertEqual("research_required", record["status"])
        self.assertEqual("research_plan", record["current_state"])
        research = record["research_plan"]
        self.assertEqual("research_required", research["status"])  # type: ignore[index]
        self.assertTrue(research["read_only"])  # type: ignore[index]
        self.assertFalse(research["mutation_allowed"])  # type: ignore[index]
        self.assertEqual(
            [{"type": "lead", "ref": "possible-docs-mcp package"}],
            research["seed_leads"],  # type: ignore[index]
        )
        self.assertIn("GitHub repository URL", research["preferred_seed_types"])  # type: ignore[index]
        self.assertIn("package name", research["preferred_seed_types"])  # type: ignore[index]
        self.assertIn("draft abstract_service_spec", " ".join(research["required_outputs"]))  # type: ignore[index]
        self.assertIn("read-only research pass", record["next_questions"][0])  # type: ignore[index]

    def test_github_url_lead_is_typed_for_research_plan(self) -> None:
        record = helper.build_onboarding_record(
            {
                "candidate_service": "possible-github-service",
                "operator_goal": "Investigate whether this repository hosts an MCP service.",
                "lead": "https://github.com/example/possible-github-service",
            },
            project_root=PROJECT_ROOT,
            issue="#52",
        )

        research = record["research_plan"]
        self.assertEqual("research_required", record["status"])
        self.assertEqual(
            [{"type": "github_url", "ref": "https://github.com/example/possible-github-service"}],
            research["seed_leads"],  # type: ignore[index]
        )

    def test_missing_credential_boundary_blocks_before_runtime_handoff(self) -> None:
        record = helper.build_onboarding_record(
            {
                "candidate_service": "github",
                "operator_goal": "Represent a token-scoped GitHub service binding.",
                "source_evidence": [{"type": "local_path", "ref": "server-instances/github/instance.json"}],
                "classification": {
                    "plan_type": "runtime_registration",
                    "localization_type": "credential_scoped",
                    "functional_type": "remote_api_tool",
                    "transport_type": "streamable_http",
                    "state_type": "credential_state",
                    "approval_type": "contextforge_dev_registry",
                },
            },
            project_root=PROJECT_ROOT,
            issue="#52",
        )

        self.assertEqual("needs_user_input", record["status"])
        self.assertEqual("classification", record["current_state"])
        gate = record["pre_runtime_workflow_gate"]
        self.assertEqual("blocked", gate["gate_status"])  # type: ignore[index]
        self.assertIn("credential_boundary", gate["missing_dimensions"])  # type: ignore[index]
        self.assertIn("credential_scope_negative_readback", _probe_layers(gate))  # type: ignore[arg-type]
        self.assertIn(
            "Which credential, account, tenant, token, or installation boundary defines this service binding?",
            record["next_questions"],
        )

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
        resumed_spec = resumed["guidance_plan"]["abstract_service_spec"]  # type: ignore[index]
        self.assertEqual("draft_generated", resumed_spec["status"])  # type: ignore[index]
        self.assertEqual("contextforge://service-specs/unknown-service/abstract/v1", resumed_spec["resource_uri"])  # type: ignore[index]
        self.assertIn("client_loading_requirement", resumed["guidance_plan"])  # type: ignore[operator]
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

    def test_cli_saves_and_resumes_from_local_ignored_session_store(self) -> None:
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
            project_root = Path(tmp)
            session_dir = project_root / "run/service-onboarding-sessions"
            session_path = session_dir / "svc-onboarding-local-store.json"
            descriptor_path = project_root / "descriptor.json"
            descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

            first = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--descriptor",
                    str(FIXTURE),
                    "--case",
                    "missing_evidence_prompts_questions",
                    "--project-root",
                    str(project_root),
                    "--issue",
                    "#52",
                    "--session-id",
                    "svc-onboarding-local-store",
                    "--save-session",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            first_output = json.loads(first.stdout)

            second = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--descriptor",
                    str(descriptor_path),
                    "--project-root",
                    str(project_root),
                    "--issue",
                    "#52",
                    "--resume-session",
                    "svc-onboarding-local-store",
                    "--save-session",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            second_output = json.loads(second.stdout)
            session_exists = session_path.exists()
            saved_output = json.loads(session_path.read_text(encoding="utf-8"))

        self.assertEqual("", first.stderr)
        self.assertEqual("", second.stderr)
        self.assertTrue(session_exists)
        self.assertEqual("needs_user_input", first_output["status"])
        self.assertEqual("local_ignored_session_file", first_output["dialogue_session"]["storage_mode"])
        self.assertTrue(first_output["dialogue_session"]["write_persistence"])
        self.assertEqual(str(session_path), first_output["dialogue_session"]["session_record_path"])
        self.assertEqual("ready_for_handoff", second_output["status"])
        self.assertEqual("previous_record", second_output["dialogue_session"]["resume_source"])
        self.assertEqual(2, second_output["dialogue_session"]["turn_index"])
        self.assertEqual("local_ignored_session_file", second_output["dialogue_session"]["storage_mode"])
        self.assertTrue(second_output["dialogue_session"]["write_persistence"])
        self.assertEqual(second_output, saved_output)

    def test_build_session_status_summarizes_resume_state_without_record_payload(self) -> None:
        previous = self.record("missing_evidence_prompts_questions")
        resumed = helper.build_onboarding_record(
            {
                "classification": {
                    "plan_type": "source_only_scaffolding",
                    "localization_type": "shared_canonical",
                    "functional_type": "search_retrieval",
                    "transport_type": "streamable_http",
                    "state_type": "stateless",
                    "approval_type": "source_only",
                },
                "source_evidence": [{"type": "package", "ref": "unknown-service"}],
            },
            project_root=PROJECT_ROOT,
            issue="#52",
            previous_record=previous,
            session_id="svc-onboarding-status",
            storage_mode=helper.LOCAL_SESSION_STORAGE_MODE,
            write_persistence=True,
            session_record_path="/tmp/project/run/service-onboarding-sessions/svc-onboarding-status.json",
        )

        summary = helper.build_session_status(resumed)

        self.assertEqual("service_onboarding_session_status", summary["summary_type"])
        self.assertEqual("svc-onboarding-status", summary["session_id"])
        self.assertEqual("unknown-service", summary["candidate_service"])
        self.assertEqual("ready_for_handoff", summary["status"])
        self.assertEqual("handoff", summary["current_state"])
        self.assertEqual(2, summary["turn_index"])
        self.assertEqual([], summary["classification_open"])
        self.assertIn("approval_type", summary["classification_known"])
        self.assertEqual("Direct native registration", summary["primary_paradigm"])
        self.assertFalse(summary["approval_required"])
        self.assertFalse(summary["mutation_allowed"])
        self.assertEqual("ready_for_pre_runtime_handoff", summary["pre_runtime_workflow_gate"]["gate_status"])
        self.assertEqual([], summary["pre_runtime_workflow_gate"]["missing_dimensions"])
        self.assertEqual(["native_transport_contract_readback"], _probe_layers(summary["pre_runtime_workflow_gate"]))
        self.assertIn(
            "What upstream docs, package names, commands, local paths, or issue links prove the service shape?",
            summary["answered_questions"],
        )
        self.assertNotIn("source_descriptor", summary)

    def test_cli_session_status_reads_local_store_without_descriptor_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            session_id = "svc-onboarding-status-cli"
            first = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--descriptor",
                    str(FIXTURE),
                    "--case",
                    "missing_evidence_prompts_questions",
                    "--project-root",
                    str(project_root),
                    "--issue",
                    "#52",
                    "--session-id",
                    session_id,
                    "--save-session",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            status = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--project-root",
                    str(project_root),
                    "--session-status",
                    session_id,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        first_output = json.loads(first.stdout)
        status_output = json.loads(status.stdout)
        self.assertEqual("", first.stderr)
        self.assertEqual("", status.stderr)
        self.assertEqual("needs_user_input", first_output["status"])
        self.assertEqual("service_onboarding_session_status", status_output["summary_type"])
        self.assertEqual(session_id, status_output["session_id"])
        self.assertEqual("source_discovery", status_output["current_state"])
        self.assertEqual(1, status_output["turn_index"])
        self.assertIn("plan_type", status_output["classification_open"])
        self.assertEqual("blocked", status_output["pre_runtime_workflow_gate"]["gate_status"])
        self.assertIn("validation_probe_plan", status_output["pre_runtime_workflow_gate"]["missing_dimensions"])
        self.assertFalse(status_output["mutation_allowed"])
        self.assertTrue(status_output["session_record_path"].endswith(f"{session_id}.json"))

    def test_cli_session_status_rejects_descriptor_or_write_combinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for extra_args in [
                ["--descriptor", str(FIXTURE)],
                ["--save-session"],
                ["--resume-session", "same-session"],
                ["--previous-record", str(FIXTURE)],
            ]:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                        "--project-root",
                        tmp,
                        "--session-status",
                        "same-session",
                        *extra_args,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertNotEqual(0, result.returncode)

    def test_list_session_statuses_returns_empty_list_for_missing_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "run/service-onboarding-sessions"

            listing = helper.list_session_statuses(session_dir)

        self.assertEqual("service_onboarding_session_list", listing["summary_type"])
        self.assertEqual(0, listing["session_count"])
        self.assertEqual([], listing["sessions"])
        self.assertFalse(listing["mutation_allowed"])

    def test_cli_list_sessions_emits_sorted_compact_statuses_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            session_dir = project_root / "run/service-onboarding-sessions"
            for session_id, case_name in [
                ("zeta-session", "missing_evidence_prompts_questions"),
                ("alpha-session", "native_http_shared_docs_source_only"),
            ]:
                subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                        "--descriptor",
                        str(FIXTURE),
                        "--case",
                        case_name,
                        "--project-root",
                        str(project_root),
                        "--issue",
                        "#52",
                        "--session-id",
                        session_id,
                        "--save-session",
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--project-root",
                    str(project_root),
                    "--list-sessions",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            output = json.loads(result.stdout)
            saved_paths = sorted(path.name for path in session_dir.glob("*.json"))

        self.assertEqual("", result.stderr)
        self.assertEqual(["alpha-session.json", "zeta-session.json"], saved_paths)
        self.assertEqual("service_onboarding_session_list", output["summary_type"])
        self.assertEqual(2, output["session_count"])
        self.assertFalse(output["mutation_allowed"])
        self.assertEqual(["alpha-session", "zeta-session"], [item["session_id"] for item in output["sessions"]])
        self.assertEqual(["ready_for_handoff", "needs_user_input"], [item["status"] for item in output["sessions"]])
        self.assertNotIn("source_descriptor", output["sessions"][0])
        self.assertTrue(output["sessions"][0]["session_record_path"].endswith("alpha-session.json"))

    def test_cli_list_sessions_rejects_descriptor_status_resume_or_write_combinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for extra_args in [
                ["--descriptor", str(FIXTURE)],
                ["--save-session"],
                ["--resume-session", "same-session"],
                ["--previous-record", str(FIXTURE)],
                ["--session-status", "same-session"],
            ]:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                        "--project-root",
                        tmp,
                        "--list-sessions",
                        *extra_args,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertNotEqual(0, result.returncode)

    def test_build_session_template_scaffolds_missing_resume_inputs(self) -> None:
        record = helper.build_onboarding_record(
            self.cases["missing_evidence_prompts_questions"]["descriptor"],  # type: ignore[arg-type]
            project_root=PROJECT_ROOT,
            issue="#52",
            session_id="missing-service-evidence",
            storage_mode=helper.LOCAL_SESSION_STORAGE_MODE,
            write_persistence=True,
            session_record_path="/tmp/project/run/service-onboarding-sessions/missing.json",
        )

        template = helper.build_session_template(record, session_record_path="/tmp/project/run/service-onboarding-sessions/missing.json")

        self.assertEqual("service_onboarding_resume_template", template["summary_type"])
        self.assertFalse(template["mutation_allowed"])
        self.assertEqual("missing-service-evidence", template["session"]["session_id"])
        self.assertEqual("needs_user_input", template["session"]["status"])
        self.assertEqual("blocked", template["pre_runtime_workflow_gate"]["gate_status"])
        self.assertIn("validation_probe_plan", template["pre_runtime_workflow_gate"]["missing_dimensions"])
        self.assertNotIn("source_descriptor", template["session"])
        self.assertIn(
            "What upstream docs, package names, commands, local paths, or issue links prove the service shape?",
            template["next_questions"],
        )
        patch = template["descriptor_patch_template"]
        self.assertEqual(
            [{"type": "<docs|package|repository|local_path|issue>", "ref": "<source reference>"}],
            patch["source_evidence"],
        )
        self.assertIn("plan_type", patch["classification"])
        self.assertIn("source_only_scaffolding", patch["classification"]["plan_type"])
        self.assertIn("validation_probe_plan", patch)
        self.assertEqual([], patch["feasibility"]["evidence_gaps"])
        self.assertIn("--resume-session missing-service-evidence", template["rerun_guidance"]["command"])
        self.assertFalse(template["rerun_guidance"]["write_persistence"])

        slugless_record = helper.build_onboarding_record(
            {
                "operator_goal": "prove footprint scaffolding",
                "source_evidence": [{"type": "docs", "ref": "https://example.invalid/service"}],
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
            session_id="slugless-service",
        )
        slugless_template = helper.build_session_template(slugless_record)
        self.assertEqual("<stable-service-slug>", slugless_template["descriptor_patch_template"]["footprint_plan"]["service_slug"])

    def test_cli_session_template_reads_store_without_rewriting_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            session_id = "svc-onboarding-template-cli"
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--descriptor",
                    str(FIXTURE),
                    "--case",
                    "missing_evidence_prompts_questions",
                    "--project-root",
                    str(project_root),
                    "--issue",
                    "#52",
                    "--session-id",
                    session_id,
                    "--save-session",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            session_path = project_root / "run/service-onboarding-sessions" / f"{session_id}.json"
            before = session_path.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--project-root",
                    str(project_root),
                    "--session-template",
                    session_id,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            after = session_path.read_text(encoding="utf-8")
            output = json.loads(result.stdout)

        self.assertEqual("", result.stderr)
        self.assertEqual(before, after)
        self.assertEqual("service_onboarding_resume_template", output["summary_type"])
        self.assertEqual(session_id, output["session"]["session_id"])
        self.assertFalse(output["mutation_allowed"])
        self.assertIn("classification", output["descriptor_patch_template"])
        self.assertIn("source_evidence", output["descriptor_patch_template"])

    def test_cli_session_template_rejects_descriptor_status_list_resume_or_write_combinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for extra_args in [
                ["--descriptor", str(FIXTURE)],
                ["--save-session"],
                ["--resume-session", "same-session"],
                ["--previous-record", str(FIXTURE)],
                ["--session-status", "same-session"],
                ["--list-sessions"],
            ]:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                        "--project-root",
                        tmp,
                        "--session-template",
                        "same-session",
                        *extra_args,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertNotEqual(0, result.returncode)

    def test_build_research_packet_seals_read_only_source_handoff(self) -> None:
        record = helper.build_onboarding_record(
            {
                "candidate_service": "possible-docs-service",
                "operator_goal": "Investigate whether this lead can become a ContextForge service.",
                "source_leads": ["possible-docs-mcp package"],
            },
            project_root=PROJECT_ROOT,
            issue="#52",
            session_id="research-packet-source-lead",
        )

        packet = helper.build_research_packet(record)

        self.assertEqual("contextforge://control-plane/schemas/service-onboarding-research-packet/v1", packet["schema_uri"])
        self.assertEqual("service_onboarding_research_packet", packet["summary_type"])
        self.assertFalse(packet["mutation_allowed"])
        self.assertTrue(packet["read_only"])
        self.assertIn("source_ready research only", packet["claim_boundary"])
        self.assertEqual("research-packet-source-lead", packet["session"]["session_id"])
        self.assertEqual(
            [{"type": "lead", "ref": "possible-docs-mcp package"}],
            packet["seed_leads"],
        )
        self.assertIn("do not call ContextForge registry", " ".join(packet["forbidden_actions"]))
        self.assertIn("draft abstract_service_spec", " ".join(packet["required_outputs"]))
        self.assertIn("source_leads", packet["descriptor_patch_contract"])
        self.assertIn("abstract_service_spec", packet["descriptor_patch_contract"])
        self.assertIn("final_narrative", packet["submission_shape"])
        self.assertIn("state explicitly that no runtime", " ".join(packet["final_narrative_requirement"]))

    def test_cli_research_packet_reads_store_without_rewriting_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            session_id = "svc-onboarding-research-packet-cli"
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--descriptor",
                    "-",
                    "--project-root",
                    str(project_root),
                    "--issue",
                    "#52",
                    "--session-id",
                    session_id,
                    "--save-session",
                ],
                input=json.dumps(
                    {
                        "candidate_service": "possible-docs-service",
                        "operator_goal": "Investigate whether this lead can become a ContextForge service.",
                        "source_leads": ["possible-docs-mcp package"],
                    }
                ),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            session_path = project_root / "run/service-onboarding-sessions" / f"{session_id}.json"
            before = session_path.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                    "--project-root",
                    str(project_root),
                    "--research-packet",
                    session_id,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            after = session_path.read_text(encoding="utf-8")
            output = json.loads(result.stdout)

        self.assertEqual("", result.stderr)
        self.assertEqual(before, after)
        self.assertEqual("service_onboarding_research_packet", output["summary_type"])
        self.assertEqual(session_id, output["session"]["session_id"])
        self.assertFalse(output["mutation_allowed"])
        self.assertTrue(output["read_only"])
        self.assertIn("possible-docs-mcp package", json.dumps(output["seed_leads"]))

    def test_cli_research_packet_rejects_descriptor_status_list_resume_template_or_write_combinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for extra_args in [
                ["--descriptor", str(FIXTURE)],
                ["--save-session"],
                ["--resume-session", "same-session"],
                ["--previous-record", str(FIXTURE)],
                ["--session-status", "same-session"],
                ["--session-template", "same-session"],
                ["--list-sessions"],
            ]:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "scripts/control_plane_service_onboarding_helper.py"),
                        "--project-root",
                        tmp,
                        "--research-packet",
                        "same-session",
                        *extra_args,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertNotEqual(0, result.returncode)

    def test_descriptor_must_be_mapping(self) -> None:
        with self.assertRaises(helper.ServiceOnboardingInputError):
            helper.build_onboarding_record(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_previous_record_must_include_source_descriptor_for_resume(self) -> None:
        with self.assertRaises(helper.ServiceOnboardingInputError):
            helper.build_onboarding_record({}, previous_record={"status": "needs_user_input"})

    def test_local_session_store_rejects_unignored_or_traversing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(helper.ServiceOnboardingInputError):
                helper.resolve_session_dir("service-onboarding-sessions", project_root=tmp)
            session_dir = helper.resolve_session_dir("run/service-onboarding-sessions", project_root=tmp)
            with self.assertRaises(helper.ServiceOnboardingInputError):
                helper.session_record_path(session_dir, "../bad")
            self.assertEqual(session_dir / "safe-session_1.json", helper.session_record_path(session_dir, "safe-session_1"))


def _blockers(record: dict[str, object]) -> list[dict[str, str]]:
    questions = set(record["next_questions"])  # type: ignore[arg-type]
    return [
        {"field": field, "question": entry["next_evidence_step"] or ""}
        for field, entry in record["classification"].items()  # type: ignore[union-attr]
        if entry["status"] != "known" and entry["next_evidence_step"] in questions
    ]


def _probe_layers(gate: object) -> list[str]:
    return [
        layer["layer"]
        for layer in gate["planned_validation_probe_layers"]  # type: ignore[index]
    ]


def _probe_layer(gate: object, name: str) -> dict[str, object]:
    for layer in gate["planned_validation_probe_layers"]:  # type: ignore[index]
        if layer["layer"] == name:
            return layer
    raise AssertionError(f"missing probe layer: {name}")


if __name__ == "__main__":
    unittest.main()
