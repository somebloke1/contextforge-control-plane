from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_contracts as contracts
import control_plane_inference_harness as harness


ASSISTANT_OUTPUT = (
    "Use ContextForge catalog readback as authority, treat client configs as discovery only, "
    "reuse any suitable shared canonical service without duplicate backend creation, keep "
    ".project/context_forge_state.json as the project-init state authority, require scoped "
    "consent for project-local writes, keep user-global trust separate, exclude real credential "
    "values from recorded surfaces, wait for target-client list-tools proof, and preserve "
    "negative tool-policy checks against untrusted metadata or comments."
)


class FakeRunner:
    def __init__(
        self,
        cases: dict[str, Any],
        *,
        assistant_output: str = ASSISTANT_OUTPUT,
        evaluator_overrides: dict[str, Any] | None = None,
        broken_provenance_role: str | None = None,
    ) -> None:
        self.cases = {case["scenario_id"]: case for case in cases["cases"]}
        self.assistant_output = assistant_output
        self.evaluator_overrides = evaluator_overrides or {}
        self.broken_provenance_role = broken_provenance_role
        self.requests: list[harness.HeadlessCommandRequest] = []

    def run(self, request: harness.HeadlessCommandRequest) -> harness.HeadlessCommandResult:
        self.requests.append(request)
        if request.role == "tested_assistant":
            stdout = self.assistant_output
        elif request.role == "evaluator":
            override = self.evaluator_overrides.get(request.scenario_id)
            stdout = override if isinstance(override, str) else json.dumps(
                override or valid_evaluator_judgment(self.cases[request.scenario_id]),
                sort_keys=True,
            )
        else:
            raise AssertionError(f"unexpected role: {request.role}")

        command = (f"fake-{request.role}", request.scenario_id)
        artifacts = (f"{request.artifact_ref_base}/fake-stdout.txt",)
        if self.broken_provenance_role == request.role:
            command = ()
            artifacts = ()
        return harness.HeadlessCommandResult(
            role=request.role,
            command=command,
            exit_code=0,
            stdout=stdout,
            stderr="",
            generated_artifact_refs=artifacts,
        )


def valid_evaluator_judgment(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": "pass",
        "failed_requirements": [],
        "likely_cause": "flaky_environment",
        "remediation_target": "prompt",
        "requirement_gap_proposal": None,
        "requirement_findings": [
            {
                "requirement_id": requirement_id,
                "result": "pass",
                "evidence_refs": ["prompt-1", "assistant-output-1"],
                "summary": f"Runner-produced assistant output satisfies {requirement_id}.",
            }
            for requirement_id in case["requirement_ids"]
        ],
    }


class ControlPlaneInferenceHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.requirements = harness.load_requirements()
        cls.cases = harness.load_inference_cases()
        cls.requirement_ids = {item["requirement_id"] for item in cls.requirements["requirements"]}

    def run_with_fake(self, **kwargs: Any) -> tuple[dict[str, Any], FakeRunner]:
        runner = FakeRunner(self.cases, **kwargs)
        evidence = harness.run_inference_cases(self.requirements, self.cases, runner=runner)
        return evidence, runner

    def test_inference_cases_cover_every_must_pass_mvs_requirement(self) -> None:
        validated = harness.validate_inference_cases(self.cases, requirements=self.requirements)
        covered = {
            requirement_id
            for case in validated["cases"]
            for requirement_id in case["requirement_ids"]
        }
        must_pass = {
            item["requirement_id"]
            for item in self.requirements["requirements"]
            if item["acceptance_gate"] == "must_pass_mvs"
        }
        self.assertEqual(must_pass, covered)
        case_types = {case["case_type"] for case in validated["cases"]}
        self.assertIn("adversarial_prompt_injection", case_types)
        self.assertIn("malicious_metadata", case_types)

    def test_fixture_authored_assistant_turns_are_rejected(self) -> None:
        cases = copy.deepcopy(self.cases)
        cases["cases"][0]["tested_assistant_turns"] = [{"turn_id": "canned", "content": "do the right thing"}]
        with self.assertRaises(harness.InferenceHarnessValidationError):
            harness.validate_inference_cases(cases, requirements=self.requirements)

    def test_fixture_authored_evaluator_judgments_and_findings_are_rejected(self) -> None:
        for key, value in (
            ("evaluator_judgment", {"verdict": "pass"}),
            ("verdict", "pass"),
            ("requirement_findings", [{"requirement_id": "cfcp-req-contextforge-authority"}]),
        ):
            with self.subTest(key=key):
                cases = copy.deepcopy(self.cases)
                cases["cases"][0][key] = value
                with self.assertRaises(harness.InferenceHarnessValidationError):
                    harness.validate_inference_cases(cases, requirements=self.requirements)

    def test_tested_assistant_prompt_uses_only_visible_context(self) -> None:
        case = self.cases["cases"][0]
        prompt = harness.build_tested_assistant_prompt(case)
        self.assertIn(case["tested_agent_visible"]["user_prompt"], prompt)
        for context in case["tested_agent_visible"]["visible_context"]:
            self.assertIn(context["content"], prompt)
        for value in case["evaluator_private_context"]["acceptance_refs"]:
            self.assertNotIn(value, prompt)
        for value in case["evaluator_private_context"]["expected_behavior"]:
            self.assertNotIn(value, prompt)
        for value in case["evaluator_rubric"]["criteria"]:
            self.assertNotIn(value, prompt)
        self.assertIn("ContextForge readback shows canonical service context7", prompt)

    def test_tested_agent_visible_rejects_role_private_structural_fields(self) -> None:
        for key, value in (
            ("evaluator_private_context", {"expected_behavior": ["hidden"]}),
            ("remediation_handoff", {"target": "prompt"}),
            ("future_evaluator_prompt", "later judge text"),
        ):
            with self.subTest(key=key):
                cases = copy.deepcopy(self.cases)
                cases["cases"][0]["tested_agent_visible"][key] = value
                with self.assertRaises(harness.InferenceHarnessValidationError):
                    harness.validate_inference_cases(cases, requirements=self.requirements)

    def test_semantic_isolation_text_is_left_to_evaluator_verdict(self) -> None:
        cases = copy.deepcopy(self.cases)
        cases["cases"][0]["tested_agent_visible"]["visible_context"][0]["content"] += (
            " The word evaluator appears in user-visible prose and is not a structural oracle field."
        )
        validated = harness.validate_inference_cases(cases, requirements=self.requirements)
        self.assertIn("evaluator appears", validated["cases"][0]["tested_agent_visible"]["visible_context"][0]["content"])

    def test_fake_runner_outputs_are_the_only_source_for_passing_evidence(self) -> None:
        evidence, runner = self.run_with_fake()
        self.assertEqual("passed", evidence["pass_fail_summary"]["overall_result"])
        self.assertEqual([], evidence["pass_fail_summary"]["requirement_gaps"])
        self.assertEqual(["tested_assistant", "evaluator"] * len(self.cases["cases"]), [req.role for req in runner.requests])

        for case_result in evidence["case_results"]:
            with self.subTest(case=case_result["scenario_id"]):
                transcript = case_result["tested_assistant_transcript"]
                assistant_entries = [entry for entry in transcript["entries"] if entry["actor"] == "assistant"]
                self.assertEqual([ASSISTANT_OUTPUT], [entry["content"] for entry in assistant_entries])
                self.assertEqual("pass", case_result["evaluator_verdict"]["verdict"])
                self.assertTrue(case_result["passed"])
                self.assertIn("x_runner_provenance", transcript)
                self.assertEqual(
                    "tested_assistant",
                    case_result["runner_provenance"]["tested_assistant"]["role"],
                )
                self.assertEqual("evaluator", case_result["runner_provenance"]["evaluator"]["role"])
                contracts.validate_artifact("evaluator_verdict", case_result["evaluator_verdict"])
                contracts.validate_artifact("evidence_ledger", case_result["evidence_ledger"])

    def test_live_codex_runner_uses_output_schema_for_evaluator_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = Path(temp_dir) / "evaluator-output.schema.json"
            runner = harness.CodexExecRunner(
                command_prefix=("codex", "exec", "--ephemeral", "--sandbox", "read-only"),
                evaluator_output_schema_path=schema_path,
            )
            request = harness.HeadlessCommandRequest(
                role="evaluator",
                scenario_id="cfcp-test",
                prompt="{}",
                artifact_ref_base="run/test/evaluator",
            )
            schema_written = runner._write_evaluator_output_schema()
            self.assertEqual(schema_path, schema_written)
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(sorted(harness.VERDICTS), schema["properties"]["verdict"]["enum"])
            self.assertEqual(
                sorted(harness.LIKELY_CAUSES),
                schema["properties"]["likely_cause"]["enum"],
            )
            self.assertIn("requirement_findings", schema["required"])

            scoped_schema = harness.evaluator_output_schema(
                requirement_ids=["cfcp-req-one"],
                transcript_entry_ids=["prompt-1", "assistant-output-1"],
            )
            schema_written = runner._write_evaluator_output_schema(scoped_schema)
            schema = json.loads(schema_written.read_text(encoding="utf-8"))
            finding_schema = schema["properties"]["requirement_findings"]["items"]["properties"]
            self.assertEqual(["cfcp-req-one"], finding_schema["requirement_id"]["enum"])
            self.assertEqual(["assistant-output-1", "prompt-1"], finding_schema["evidence_refs"]["items"]["enum"])

            command_parts = [
                *runner.command_prefix,
                "--cd",
                str(harness.REPO_ROOT),
                "--output-last-message",
                "/tmp/last-message.txt",
            ]
            if request.role == "evaluator":
                command_parts.extend(["--output-schema", str(schema_path)])
            self.assertIn("--output-schema", command_parts)

            assistant_request = harness.HeadlessCommandRequest(
                role="tested_assistant",
                scenario_id="cfcp-test",
                prompt="hello",
                artifact_ref_base="run/test/assistant",
            )
            assistant_command_parts = [
                *runner.command_prefix,
                "--cd",
                str(harness.REPO_ROOT),
                "--output-last-message",
                "/tmp/last-message.txt",
            ]
            if assistant_request.role == "evaluator":
                assistant_command_parts.extend(["--output-schema", str(schema_path)])
            self.assertNotIn("--output-schema", assistant_command_parts)

    def test_live_codex_runner_accepts_explicit_model_prefix(self) -> None:
        runner = harness.CodexExecRunner(
            command_prefix=("codex", "exec", "--ephemeral", "--sandbox", "read-only", "--model", "gpt-5-4-mini")
        )
        self.assertEqual(
            ("codex", "exec", "--ephemeral", "--sandbox", "read-only", "--model", "gpt-5-4-mini"),
            runner.command_prefix,
        )

    def test_fake_evaluator_pass_without_required_transcript_evidence_fails_closed(self) -> None:
        case = self.cases["cases"][0]
        missing_assistant_output_ref = valid_evaluator_judgment(case)
        missing_assistant_output_ref["requirement_findings"][0]["evidence_refs"] = ["prompt-1"]
        runner = FakeRunner(
            self.cases,
            assistant_output="Create a project-local context7 wrapper and treat Claude config as the identity.",
            evaluator_overrides={case["scenario_id"]: missing_assistant_output_ref},
        )
        with self.assertRaises(harness.InferenceHarnessValidationError):
            harness.run_inference_cases(self.requirements, self.cases, runner=runner)

        missing_required_requirement = valid_evaluator_judgment(case)
        missing_required_requirement["requirement_findings"] = missing_required_requirement["requirement_findings"][:1]
        runner = FakeRunner(
            self.cases,
            assistant_output="Create a project-local context7 wrapper and treat Claude config as the identity.",
            evaluator_overrides={case["scenario_id"]: missing_required_requirement},
        )
        with self.assertRaises(harness.InferenceHarnessValidationError):
            harness.run_inference_cases(self.requirements, self.cases, runner=runner)

    def test_evaluator_request_schema_is_scoped_to_case_transcript_entries(self) -> None:
        evidence, runner = self.run_with_fake()
        self.assertEqual("passed", evidence["pass_fail_summary"]["overall_result"])
        evaluator_requests = [request for request in runner.requests if request.role == "evaluator"]
        self.assertTrue(evaluator_requests)
        for request in evaluator_requests:
            with self.subTest(scenario=request.scenario_id):
                self.assertIsNotNone(request.output_schema)
                schema = request.output_schema or {}
                finding_schema = schema["properties"]["requirement_findings"]["items"]["properties"]
                requirement_enum = set(finding_schema["requirement_id"]["enum"])
                evidence_enum = set(finding_schema["evidence_refs"]["items"]["enum"])
                case = next(case for case in self.cases["cases"] if case["scenario_id"] == request.scenario_id)
                self.assertEqual(set(case["requirement_ids"]), requirement_enum)
                self.assertIn("assistant-output-1", evidence_enum)
                self.assertNotIn(f"transcript-20260530T202154Z-w12-z1-inference-contract-{request.scenario_id}", evidence_enum)
                self.assertIn("allowed_evidence_refs", request.prompt)
                self.assertIn("do not cite transcript ids", request.prompt)

    def test_nonzero_runner_error_includes_stderr_tail(self) -> None:
        result = harness.HeadlessCommandResult(
            role="evaluator",
            command=("codex", "exec"),
            exit_code=1,
            stdout="",
            stderr="first line\nmodel rejected output schema",
            generated_artifact_refs=("run/test/evaluator/stderr.txt",),
        )
        with self.assertRaisesRegex(harness.InferenceHarnessValidationError, "model rejected output schema"):
            harness._runner_provenance(result, expected_role="evaluator", prompt="prompt")

    def test_non_pass_inconclusive_requirement_gap_invalid_json_missing_findings_and_missing_provenance_fail(self) -> None:
        case = self.cases["cases"][0]

        for verdict in ("fail", "inconclusive", "requirement_gap"):
            with self.subTest(verdict=verdict):
                judgment = valid_evaluator_judgment(case)
                judgment["verdict"] = verdict
                judgment["likely_cause"] = "agent_inference_failure" if verdict != "requirement_gap" else "requirement_gap"
                judgment["remediation_target"] = "prompt" if verdict != "requirement_gap" else "rfc"
                judgment["failed_requirements"] = ["cfcp-req-contextforge-authority"] if verdict == "fail" else []
                judgment["requirement_findings"][0]["result"] = "fail" if verdict == "fail" else "inconclusive"
                judgment["requirement_gap_proposal"] = "Clarify acceptance wording." if verdict == "requirement_gap" else None
                runner = FakeRunner(self.cases, evaluator_overrides={case["scenario_id"]: judgment})
                evidence = harness.run_inference_cases(self.requirements, self.cases, runner=runner)
                self.assertEqual("failed", evidence["pass_fail_summary"]["overall_result"])
                self.assertIn(case["scenario_id"], evidence["pass_fail_summary"]["failed_case_ids"])

        for label, override in (
            ("invalid-json", "{not json"),
            ("missing-findings", {key: value for key, value in valid_evaluator_judgment(case).items() if key != "requirement_findings"}),
            ("unknown-cause", {**valid_evaluator_judgment(case), "likely_cause": "unknown"}),
            ("unknown-remediation", {**valid_evaluator_judgment(case), "remediation_target": "unknown"}),
        ):
            with self.subTest(label=label):
                runner = FakeRunner(self.cases, evaluator_overrides={case["scenario_id"]: override})
                with self.assertRaises(harness.InferenceHarnessValidationError):
                    harness.run_inference_cases(self.requirements, self.cases, runner=runner)

        with self.subTest(label="missing-runner-provenance"):
            runner = FakeRunner(self.cases, broken_provenance_role="tested_assistant")
            with self.assertRaises(harness.InferenceHarnessValidationError):
                harness.run_inference_cases(self.requirements, self.cases, runner=runner)

    def test_each_mvs_requirement_maps_to_passing_evaluator_verdict_refs_from_fake_runner(self) -> None:
        evidence, _runner = self.run_with_fake()
        rows = evidence["requirement_evaluator_verdict_map"]
        must_pass = {
            item["requirement_id"]
            for item in self.requirements["requirements"]
            if item["acceptance_gate"] == "must_pass_mvs"
        }
        self.assertEqual(must_pass, {row["requirement_id"] for row in rows})
        for row in rows:
            with self.subTest(requirement=row["requirement_id"]):
                self.assertTrue(row["scenario_ids"])
                self.assertTrue(row["passing_evaluator_verdict_refs"])
                self.assertTrue(row["all_verdicts_pass"])
                self.assertFalse(row["blocker_if_not_pass"])
                self.assertTrue(all(verdict == "pass" for verdict in row["verdicts"]))
                self.assertTrue(all(ref["ref"].endswith("/evaluator-verdict.json") for ref in row["passing_evaluator_verdict_refs"]))

    def test_remediation_handoff_omits_role_private_material_from_allowed_context(self) -> None:
        case = self.cases["cases"][0]
        judgment = valid_evaluator_judgment(case)
        judgment["verdict"] = "fail"
        judgment["failed_requirements"] = ["cfcp-req-contextforge-authority"]
        judgment["likely_cause"] = "agent_inference_failure"
        judgment["remediation_target"] = "prompt"
        judgment["requirement_findings"][0]["result"] = "fail"

        runner = FakeRunner(self.cases, evaluator_overrides={case["scenario_id"]: judgment})
        evidence = harness.run_inference_cases(self.requirements, self.cases, runner=runner)
        failed_case = next(
            item for item in evidence["case_results"] if item["scenario_id"] == "cfcp-infer-authority-shared-service"
        )
        handoff = failed_case["remediation_handoff"]
        self.assertIsNotNone(handoff)
        allowed_context = " ".join(handoff["allowed_context"])
        self.assertNotIn("hidden", allowed_context)
        self.assertNotIn("oracle", allowed_context)
        self.assertNotIn("future", allowed_context)
        self.assertIn("future evaluator prompts", " ".join(handoff["forbidden_context"]))
        self.assertEqual(["cfcp-req-contextforge-authority"], handoff["failed_requirements"])


if __name__ == "__main__":
    unittest.main()
