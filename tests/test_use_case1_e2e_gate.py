from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py"
RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-1-dialogue.py"
UC2_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-2-e2e-evidence.py"
UC2_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-2-dialogue.py"
UC3_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-3-e2e-evidence.py"
UC3_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-3-dialogue.py"
UC4_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-4-e2e-evidence.py"
UC4_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-4-dialogue.py"
UC5_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-5-e2e-evidence.py"
UC5_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-5-dialogue.py"
UC6_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-6-e2e-evidence.py"
UC6_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-6-dialogue.py"
UC7_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-7-e2e-evidence.py"
UC7_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-7-dialogue.py"
UC8_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-8-e2e-evidence.py"
UC8_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-8-dialogue.py"
UC9_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-9-e2e-evidence.py"
UC9_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-9-dialogue.py"
UC10_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-10-e2e-evidence.py"
UC10_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-10-dialogue.py"
UC11_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-11-e2e-evidence.py"
UC11_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-11-dialogue.py"
UC12_VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-12-e2e-evidence.py"
UC12_RUNNER = ROOT / "docker/client-harness/scripts/run-use-case-12-dialogue.py"
STRUCTURAL_VERIFIER = ROOT / "docker/client-harness/scripts/dialogue_structural_verifier.py"
METHOD_DOC = ROOT / "docker/client-harness/DIALOGUE_EVALUATION_METHOD.md"
DIALOGUE_SKILL = ROOT / ".codex/skills/code-assistant-dialogue-validation/SKILL.md"
CONTROL_PLANE_SKILL = ROOT / ".codex/skills/contextforge-control-plane/SKILL.md"
CONTROL_PLANE_EVIDENCE = ROOT / ".codex/skills/contextforge-control-plane/references/evidence-and-tests.md"
DISPATCH_CARD = ROOT / ".codex/skills/contextforge-agent-dispatch-matrix/references/dispatch-card.md"
PIPELINE_SPEC = ROOT / "holistic_orchestrated_pipeline_spec.md"


class UseCase1E2EGateTests(unittest.TestCase):
    def run_verifier(
        self,
        client: str,
        evidence_text: str,
        metadata: dict[str, Any],
        *extra: str,
    ) -> tuple[int, dict[str, object], str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / f"{client}.md"
            metadata_path = tmp_path / f"{client}-metadata.json"
            evidence.write_text(evidence_text, encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--client",
                    client,
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    *extra,
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        return completed.returncode, json.loads(completed.stdout), completed.stderr

    def valid_metadata(self, client: str = "opencode", session_id: str = "ses_structural") -> dict[str, Any]:
        reset_client = "codex-cli" if client == "codex" else client
        return {
            "use_case": "use-case-1",
            "client": client,
            "session_id": session_id,
            "container": f"cf-uc1-{client}-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
                "reset_client": reset_client,
            },
            "reset_json": {
                "ok": True,
                "client": reset_client,
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": client,
                "session_id": session_id,
                "step_generations": [
                    {
                        "turn": 1,
                        "model_dependent": True,
                        "returncode": 0,
                        "timeout": False,
                    },
                    {
                        "turn": 2,
                        "model_dependent": True,
                        "returncode": 0,
                        "timeout": False,
                    },
                    {
                        "turn": 3,
                        "model_dependent": True,
                        "returncode": 0,
                        "timeout": False,
                    },
                ],
                "totals": {
                    "prompt_count": 3,
                    "generation_step_count": 3,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turn1", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "reset": {"returncode": 0, "timeout": False},
                "launch": {"returncode": 0, "timeout": False},
                "runtime": {"returncode": 0, "timeout": False},
                "turn_1": {"returncode": 0, "timeout": False},
                "turn_2": {"returncode": 0, "timeout": False},
                "turn_3": {"returncode": 0, "timeout": False},
            },
            "semantic_criteria": [
                "clean_start",
                "natural_first_prompt",
                "service_selection",
                "approval_and_apply",
                "reload_boundary",
                "no_post_install_validation",
            ],
        }

    def test_verifier_checks_structure_not_dialogue_meaning(self) -> None:
        code, result, stderr = self.run_verifier(
            "opencode",
            "arbitrary non-empty evidence text; semantic meaning is evaluator-owned",
            self.valid_metadata(),
            "--session-id",
            "ses_structural",
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])
        self.assertTrue(result["semantic_evaluation_required"])
        self.assertNotIn("semantic_observations", result)
        self.assertIn("matched strings", result["deterministic_boundary"])

    def test_verifier_accepts_codex_structural_metadata(self) -> None:
        code, result, stderr = self.run_verifier(
            "codex",
            "arbitrary non-empty Codex evidence text; semantic meaning is evaluator-owned",
            self.valid_metadata(client="codex", session_id="019ee47e-a6fd-7e10-a6c7-c8cb398ce460"),
            "--session-id",
            "019ee47e-a6fd-7e10-a6c7-c8cb398ce460",
        )

        self.assertEqual("", stderr)
        self.assertEqual(0, code, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_verifier_rejects_structural_failure_without_scoring_prose(self) -> None:
        metadata = self.valid_metadata()
        metadata["required_command_statuses"]["turn_2"] = {"returncode": 1, "timeout": False}

        code, result, stderr = self.run_verifier("opencode", "non-empty", metadata)

        self.assertEqual("", stderr)
        self.assertNotEqual(0, code)
        failure_codes = {failure["code"] for failure in result["failures"]}  # type: ignore[index]
        self.assertIn("required_command_nonzero", failure_codes)
        self.assertNotIn("semantic_observations", result)

    def test_dialogue_skill_records_structure_not_meaning_restriction(self) -> None:
        text = DIALOGUE_SKILL.read_text(encoding="utf-8")

        self.assertIn("They may check structure, but not meaning", text)
        self.assertIn("matched strings", text)
        self.assertIn("regexes", text)
        self.assertIn("structured model output", text)
        self.assertIn("paired with non-deterministic evaluator", text)

    def test_pipeline_spec_records_structure_not_meaning_restriction(self) -> None:
        text = PIPELINE_SPEC.read_text(encoding="utf-8")

        self.assertIn("They may check structure, but not meaning", text)
        self.assertIn("No test, gate, score criterion, or acceptance claim", text)
        self.assertIn("declared structured model output such as JSON", text)
        self.assertIn("paired with non-deterministic evaluator review", text)

    def test_runner_and_shared_verifier_emit_metadata_contract(self) -> None:
        runner_text = RUNNER.read_text(encoding="utf-8")
        verifier_text = STRUCTURAL_VERIFIER.read_text(encoding="utf-8")
        use_case_verifier_text = VERIFIER.read_text(encoding="utf-8")

        self.assertIn("build_structural_metadata", runner_text)
        self.assertIn("--metadata", runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("codex-cli-authenticated", runner_text)
        self.assertIn("extract_codex_session_id", runner_text)
        self.assertIn("--dangerously-bypass-hook-trust", runner_text)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", runner_text)
        self.assertIn("deterministic_checks_are_structural_only", runner_text)
        self.assertIn("semantic_acceptance", runner_text)
        self.assertIn("verify_dialogue_structure", verifier_text)
        self.assertIn("check_generation_report", verifier_text)
        self.assertIn("semantic_criteria_for", verifier_text)
        self.assertNotIn("import re", verifier_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', use_case_verifier_text)

    def test_use_case2_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC2_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC2_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("codex-cli-authenticated", runner_text)
        self.assertIn("extract_codex_session_id", runner_text)
        self.assertIn("--dangerously-bypass-hook-trust", runner_text)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", runner_text)
        self.assertIn("reset_client_name(client)", runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case2_verifier_accepts_codex_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-2",
            "client": "codex",
            "session_id": "019ee484-uc2-codex",
            "container": "cf-uc2-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
                "reset_client": "codex-cli",
            },
            "reset_json": {
                "ok": True,
                "client": "codex-cli",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": "codex",
                "session_id": "019ee484-uc2-codex",
                "step_generations": [
                    {
                        "turn": 1,
                        "model_dependent": True,
                        "returncode": 0,
                        "timeout": False,
                    }
                ],
                "totals": {
                    "prompt_count": 1,
                    "generation_step_count": 1,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turn", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "setup": {"returncode": 0, "timeout": False},
                "launch": {"returncode": 0, "timeout": False},
                "runtime": {"returncode": 0, "timeout": False},
                "fixture": {"returncode": 0, "timeout": False},
                "turn": {"returncode": 0, "timeout": False},
            },
            "semantic_criteria": [
                "natural_user_prompts",
                "initialized_tool_availability",
                "hidden_instruction_boundary",
                "non_actions",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "codex-uc2.md"
            metadata_path = tmp_path / "codex-uc2-metadata.json"
            evidence.write_text("non-empty UC2 Codex evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC2_VERIFIER),
                    "--client",
                    "codex",
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "019ee484-uc2-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_use_case3_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC3_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC3_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("codex-cli-authenticated", runner_text)
        self.assertIn("extract_codex_session_id", runner_text)
        self.assertIn("--dangerously-bypass-hook-trust", runner_text)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", runner_text)
        self.assertIn("reset_client_name(client)", runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case3_verifier_accepts_codex_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-3",
            "client": "codex",
            "session_id": "019ee484-uc3-codex",
            "container": "cf-uc3-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
                "reset_client": "codex-cli",
            },
            "reset_json": {
                "ok": True,
                "client": "codex-cli",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": "codex",
                "session_id": "019ee484-uc3-codex",
                "step_generations": [
                    {
                        "turn": 1,
                        "model_dependent": True,
                        "returncode": 0,
                        "timeout": False,
                    }
                ],
                "totals": {
                    "prompt_count": 1,
                    "generation_step_count": 1,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turn", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "setup": {"returncode": 0, "timeout": False},
                "launch": {"returncode": 0, "timeout": False},
                "runtime": {"returncode": 0, "timeout": False},
                "fixture": {"returncode": 0, "timeout": False},
                "turn": {"returncode": 0, "timeout": False},
            },
            "semantic_criteria": [
                "natural_user_prompts",
                "initialized_capability_summary",
                "hidden_instruction_boundary",
                "non_actions",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "codex-uc3.md"
            metadata_path = tmp_path / "codex-uc3-metadata.json"
            evidence.write_text("non-empty UC3 Codex evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC3_VERIFIER),
                    "--client",
                    "codex",
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "019ee484-uc3-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_use_case7_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC7_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC7_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("uc3.reset_client_name(args.client)", runner_text)
        self.assertIn("uc3.compose_service_name(args.client)", runner_text)
        self.assertIn("uc3.extract_codex_session_id", runner_text)
        self.assertIn("codex-cli-authenticated", runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case8_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC8_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC8_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("uc3.reset_client_name(args.client)", runner_text)
        self.assertIn("uc3.build_service_name(args.client)", runner_text)
        self.assertIn("uc3.compose_service_name(args.client)", runner_text)
        self.assertIn("uc3.codex_empty_api_key_env_args", runner_text)
        self.assertIn("uc1.extract_codex_session_id", runner_text)
        self.assertIn('"compose_service": uc3.compose_service_name(client)', runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case11_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC11_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC11_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("uc3.reset_client_name(args.client)", runner_text)
        self.assertIn("uc3.build_service_name(args.client)", runner_text)
        self.assertIn("uc3.compose_service_name(args.client)", runner_text)
        self.assertIn("uc3.codex_empty_api_key_env_args", runner_text)
        self.assertIn("uc1.extract_codex_session_id", runner_text)
        self.assertIn('"compose_service": uc3.compose_service_name(client)', runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case12_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC12_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC12_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("uc3.reset_client_name(args.client)", runner_text)
        self.assertIn("uc3.build_service_name(args.client)", runner_text)
        self.assertIn("uc3.compose_service_name(args.client)", runner_text)
        self.assertIn("uc3.codex_empty_api_key_env_args", runner_text)
        self.assertIn("uc1.extract_codex_session_id", runner_text)
        self.assertIn("codex-cli-authenticated", runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case12_verifier_accepts_codex_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-12",
            "client": "codex",
            "session_id": "019ee484-uc12-codex",
            "container": "cf-uc12-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
                "same_session_required": True,
                "source_only_onboarding_record": True,
                "reset_client": "codex-cli",
                "compose_service": "codex-cli-authenticated",
            },
            "reset_json": {
                "ok": True,
                "client": "codex-cli",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "source_onboarding_record": {
                "candidate_service": "calendar-notes",
                "mutation_allowed": False,
                "status": "source_only_plan",
            },
            "candidate_service_boundary": {
                "project_service_registered": False,
                "target_client_projection_created": False,
                "runtime_service_started": False,
                "client_tool_visibility_claimed": False,
            },
            "generation_report": {
                "model_dependent": True,
                "client": "codex",
                "session_id": "019ee484-uc12-codex",
                "step_generations": [
                    {"turn": 1, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 2, "model_dependent": True, "returncode": 0, "timeout": False},
                ],
                "totals": {
                    "prompt_count": 2,
                    "generation_step_count": 2,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turns", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "source_record": {"returncode": 0, "timeout": False},
                "setup": {"returncode": 0, "timeout": False},
                "launch": {"returncode": 0, "timeout": False},
                "runtime": {"returncode": 0, "timeout": False},
                "fixture": {"returncode": 0, "timeout": False},
                "turn_1": {"returncode": 0, "timeout": False},
                "turn_2": {"returncode": 0, "timeout": False},
            },
            "semantic_criteria": [
                "clean_initialized_fixture",
                "natural_uncataloged_prompts",
                "structured_onboarding_process",
                "source_only_plan_or_handoff",
                "project_graph_projection_boundary",
                "credential_and_secret_boundary",
                "non_actions_and_approval_gate",
                "evidence_package_integrity",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "uc12-codex.md"
            metadata_path = tmp_path / "uc12-codex-metadata.json"
            evidence.write_text("non-empty UC12 Codex evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC12_VERIFIER),
                    "--client",
                    "codex",
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "019ee484-uc12-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_use_case9_runner_and_verifier_support_codex_cross_client_set(self) -> None:
        runner_text = UC9_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC9_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('CLIENTS = ("pi", "opencode", "codex")', runner_text)
        self.assertIn("uc3.reset_client_name(client)", runner_text)
        self.assertIn("uc3.build_service_name(client)", runner_text)
        self.assertIn("uc3.compose_service_name(client)", runner_text)
        self.assertIn("uc3.codex_empty_api_key_env_args", runner_text)
        self.assertIn("uc1.extract_codex_session_id", runner_text)
        self.assertIn("target_clients_include_all_clients", runner_text)
        self.assertIn("context7_enabled_for_all", runner_text)
        self.assertIn('CLIENT_KEY = "-".join(CLIENTS)', runner_text)
        self.assertIn('TARGET_CLIENTS = ("pi", "opencode", "codex")', verifier_text)
        self.assertIn("target_clients_include_all_clients", verifier_text)
        self.assertIn("context7_enabled_for_all", verifier_text)

    def test_use_case9_verifier_accepts_three_client_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-9",
            "client": "pi-opencode-codex",
            "session_id": "uc9-pi|ses_uc9|019ee484-uc9-codex",
            "container": "cf-uc9-pi-runner,cf-uc9-opencode-runner,cf-uc9-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
            },
            "reset_json": {
                "ok": True,
                "client": "pi-opencode-codex",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": "pi-opencode-codex",
                "session_id": "uc9-pi|ses_uc9|019ee484-uc9-codex",
                "step_generations": [
                    {"turn": 1, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 2, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 3, "model_dependent": True, "returncode": 0, "timeout": False},
                ],
                "totals": {
                    "prompt_count": 3,
                    "generation_step_count": 3,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turns", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "setup_pi": {"returncode": 0, "timeout": False},
                "setup_opencode": {"returncode": 0, "timeout": False},
                "setup_codex": {"returncode": 0, "timeout": False},
                "launch_pi": {"returncode": 0, "timeout": False},
                "launch_opencode": {"returncode": 0, "timeout": False},
                "launch_codex": {"returncode": 0, "timeout": False},
                "runtime_pi": {"returncode": 0, "timeout": False},
                "runtime_opencode": {"returncode": 0, "timeout": False},
                "runtime_codex": {"returncode": 0, "timeout": False},
                "fixture_pi": {"returncode": 0, "timeout": False},
                "fixture_opencode": {"returncode": 0, "timeout": False},
                "fixture_codex": {"returncode": 0, "timeout": False},
                "turn_pi": {"returncode": 0, "timeout": False},
                "turn_opencode": {"returncode": 0, "timeout": False},
                "turn_codex": {"returncode": 0, "timeout": False},
            },
            "cross_client_comparison": {
                "project_root_workspace": True,
                "state_status_initialized": True,
                "state_revision_present": True,
                "target_clients_include_all_clients": True,
                "enabled_services_aligned": True,
                "context7_enabled_for_all": True,
                "client_import_surfaces_present": True,
                "structured_comparison_only": True,
            },
            "semantic_criteria": [
                "natural_user_prompts",
                "cross_client_state_consistency",
                "client_specific_tool_name_honesty",
                "same_project_no_onboarding_restart",
                "hidden_instruction_boundary",
                "non_actions",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "uc9.md"
            metadata_path = tmp_path / "uc9-metadata.json"
            evidence.write_text("non-empty UC9 evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC9_VERIFIER),
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "uc9-pi|ses_uc9|019ee484-uc9-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_use_case10_runner_and_verifier_support_codex_cross_client_refresh(self) -> None:
        runner_text = UC10_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC10_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('CLIENTS = ("pi", "opencode", "codex")', runner_text)
        self.assertIn("uc3.reset_client_name(client)", runner_text)
        self.assertIn("uc3.build_service_name(client)", runner_text)
        self.assertIn("uc3.compose_service_name(client)", runner_text)
        self.assertIn("uc3.codex_empty_api_key_env_args", runner_text)
        self.assertIn("uc1.extract_codex_session_id", runner_text)
        self.assertIn("target_clients_include_all_clients", runner_text)
        self.assertIn("len(CLIENTS) + 1", runner_text)
        self.assertIn('TARGET_CLIENTS = ("pi", "opencode", "codex")', verifier_text)
        self.assertIn("len(TARGET_CLIENTS) * 2", verifier_text)
        self.assertIn("target_clients_include_all_clients", verifier_text)

    def test_use_case10_verifier_accepts_three_client_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-10",
            "client": "pi-opencode-codex",
            "session_id": "uc10-pi|ses_uc10|019ee484-uc10-codex",
            "container": "cf-uc10-pi-runner,cf-uc10-opencode-runner,cf-uc10-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
            },
            "reset_json": {
                "ok": True,
                "client": "pi-opencode-codex",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": "pi-opencode-codex",
                "session_id": "uc10-pi|ses_uc10|019ee484-uc10-codex",
                "step_generations": [
                    {"turn": 1, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 2, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 3, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 4, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 5, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 6, "model_dependent": True, "returncode": 0, "timeout": False},
                ],
                "totals": {
                    "prompt_count": 6,
                    "generation_step_count": 6,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turns", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "setup_pi": {"returncode": 0, "timeout": False},
                "setup_opencode": {"returncode": 0, "timeout": False},
                "setup_codex": {"returncode": 0, "timeout": False},
                "launch_pi": {"returncode": 0, "timeout": False},
                "launch_opencode": {"returncode": 0, "timeout": False},
                "launch_codex": {"returncode": 0, "timeout": False},
                "runtime_pi": {"returncode": 0, "timeout": False},
                "runtime_opencode": {"returncode": 0, "timeout": False},
                "runtime_codex": {"returncode": 0, "timeout": False},
                "fixture_pi": {"returncode": 0, "timeout": False},
                "fixture_opencode": {"returncode": 0, "timeout": False},
                "fixture_codex": {"returncode": 0, "timeout": False},
                "reload_ack_pi": {"returncode": 0, "timeout": False},
                "reload_ack_opencode": {"returncode": 0, "timeout": False},
                "reload_ack_codex": {"returncode": 0, "timeout": False},
                "state_change_pi": {"returncode": 0, "timeout": False},
                "state_change_opencode": {"returncode": 0, "timeout": False},
                "state_change_codex": {"returncode": 0, "timeout": False},
                "fixture_after_pi": {"returncode": 0, "timeout": False},
                "fixture_after_opencode": {"returncode": 0, "timeout": False},
                "fixture_after_codex": {"returncode": 0, "timeout": False},
                "turn_1_pi": {"returncode": 0, "timeout": False},
                "turn_2_opencode": {"returncode": 0, "timeout": False},
                "turn_3_codex": {"returncode": 0, "timeout": False},
                "turn_4_pi": {"returncode": 0, "timeout": False},
                "turn_5_opencode": {"returncode": 0, "timeout": False},
                "turn_6_codex": {"returncode": 0, "timeout": False},
            },
            "refresh_comparison": {
                "project_root_workspace": True,
                "baseline_initialized": True,
                "after_initialized": True,
                "revision_increased": True,
                "enabled_services_changed": True,
                "baseline_context7_only": True,
                "after_includes_context7_and_mentality": True,
                "target_clients_include_all_clients": True,
                "structured_comparison_only": True,
            },
            "semantic_criteria": [
                "natural_user_prompts",
                "state_change_refresh_detected",
                "updated_capabilities_visible_or_bounded",
                "stale_tools_not_presented_as_current",
                "hidden_instruction_boundary",
                "non_actions",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "uc10.md"
            metadata_path = tmp_path / "uc10-metadata.json"
            evidence.write_text("non-empty UC10 evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC10_VERIFIER),
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "uc10-pi|ses_uc10|019ee484-uc10-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_use_case4_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC4_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC4_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("codex-cli-authenticated", runner_text)
        self.assertIn("extract_codex_session_id", runner_text)
        self.assertIn("--dangerously-bypass-hook-trust", runner_text)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", runner_text)
        self.assertIn("reset_client_name(client)", runner_text)
        self.assertIn("compose_service_name(client)", runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case4_verifier_accepts_codex_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-4",
            "client": "codex",
            "session_id": "019ee484-uc4-codex",
            "container": "cf-uc4-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
                "reset_client": "codex-cli",
                "compose_service": "codex-cli-authenticated",
            },
            "reset_json": {
                "ok": True,
                "client": "codex-cli",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": "codex",
                "session_id": "019ee484-uc4-codex",
                "step_generations": [
                    {
                        "turn": 1,
                        "model_dependent": True,
                        "returncode": 0,
                        "timeout": False,
                    }
                ],
                "totals": {
                    "prompt_count": 1,
                    "generation_step_count": 1,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turn", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "setup": {"returncode": 0, "timeout": False},
                "launch": {"returncode": 0, "timeout": False},
                "runtime": {"returncode": 0, "timeout": False},
                "fixture": {"returncode": 0, "timeout": False},
                "turn": {"returncode": 0, "timeout": False},
            },
            "semantic_criteria": [
                "natural_user_prompts",
                "governance_read_only_answer",
                "hidden_instruction_boundary",
                "non_actions",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "codex-uc4.md"
            metadata_path = tmp_path / "codex-uc4-metadata.json"
            evidence.write_text("non-empty UC4 Codex evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC4_VERIFIER),
                    "--client",
                    "codex",
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "019ee484-uc4-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_use_case5_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC5_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC5_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("uc1.reset_client_name(args.client)", runner_text)
        self.assertIn("uc1.compose_service_name(args.client)", runner_text)
        self.assertIn("uc1.extract_codex_session_id", runner_text)
        self.assertIn("codex_empty_api_key_env_args", runner_text)
        self.assertIn("uc1.compose_service_name(client)", runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case5_verifier_accepts_codex_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-5",
            "shape": "single",
            "client": "codex",
            "session_id": "019ee484-uc5-codex",
            "container": "cf-uc5-single-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
                "reset_client": "codex-cli",
                "compose_service": "codex-cli-authenticated",
            },
            "reset_json": {
                "ok": True,
                "client": "codex-cli",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": "codex",
                "session_id": "019ee484-uc5-codex",
                "step_generations": [
                    {"turn": 1, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 2, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 3, "model_dependent": True, "returncode": 0, "timeout": False},
                ],
                "totals": {
                    "prompt_count": 3,
                    "generation_step_count": 3,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turn1", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "reset": {"returncode": 0, "timeout": False},
                "launch": {"returncode": 0, "timeout": False},
                "runtime": {"returncode": 0, "timeout": False},
                "turn_1": {"returncode": 0, "timeout": False},
                "turn_2": {"returncode": 0, "timeout": False},
                "turn_3": {"returncode": 0, "timeout": False},
            },
            "semantic_criteria": [
                "natural_user_prompts",
                "service_selection_plan_apply_readback",
                "shape_coverage",
                "reload_or_new_session_boundary",
                "hidden_instruction_boundary",
                "non_actions",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "codex-uc5.md"
            metadata_path = tmp_path / "codex-uc5-metadata.json"
            evidence.write_text("non-empty UC5 Codex evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC5_VERIFIER),
                    "--client",
                    "codex",
                    "--shape",
                    "single",
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "019ee484-uc5-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_use_case6_runner_and_verifier_support_codex(self) -> None:
        runner_text = UC6_RUNNER.read_text(encoding="utf-8")
        verifier_text = UC6_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('choices=["pi", "opencode", "codex"]', runner_text)
        self.assertIn("uc1.reset_client_name(args.client)", runner_text)
        self.assertIn("uc1.compose_service_name(args.client)", runner_text)
        self.assertIn("uc1.extract_codex_session_id", runner_text)
        self.assertIn("codex_empty_api_key_env_args", runner_text)
        self.assertIn("uc1.compose_service_name(client)", runner_text)
        self.assertIn('choices=["pi", "opencode", "codex"]', verifier_text)

    def test_use_case6_verifier_accepts_codex_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-6",
            "shape": "decline",
            "client": "codex",
            "session_id": "019ee484-uc6-codex",
            "container": "cf-uc6-decline-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
                "reset_client": "codex-cli",
                "compose_service": "codex-cli-authenticated",
            },
            "reset_json": {
                "ok": True,
                "client": "codex-cli",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": "codex",
                "session_id": "019ee484-uc6-codex",
                "step_generations": [
                    {"turn": 1, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 2, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 3, "model_dependent": True, "returncode": 0, "timeout": False},
                    {"turn": 4, "model_dependent": True, "returncode": 0, "timeout": False},
                ],
                "totals": {
                    "prompt_count": 4,
                    "generation_step_count": 4,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turn1", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "reset": {"returncode": 0, "timeout": False},
                "launch": {"returncode": 0, "timeout": False},
                "runtime": {"returncode": 0, "timeout": False},
                "state_readback": {"returncode": 0, "timeout": False},
                "turn_1": {"returncode": 0, "timeout": False},
                "turn_2": {"returncode": 0, "timeout": False},
                "turn_3": {"returncode": 0, "timeout": False},
                "turn_4": {"returncode": 0, "timeout": False},
            },
            "decision_state_readback": {
                "state_exists": True,
                "client": "codex",
                "expected_binding_prefix": "context7:canonical",
                "state_status": "initialized",
                "state_revision": 1,
                "decision_binding": "context7:canonical",
                "decision_state": "declined",
                "active_service_absent": True,
                "target_client_active_import_absent": True,
            },
            "semantic_criteria": [
                "natural_user_prompts",
                "decline_or_defer_recorded_without_import",
                "continued_available_capabilities",
                "hidden_instruction_boundary",
                "non_actions",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "codex-uc6.md"
            metadata_path = tmp_path / "codex-uc6-metadata.json"
            evidence.write_text("non-empty UC6 Codex evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC6_VERIFIER),
                    "--client",
                    "codex",
                    "--shape",
                    "decline",
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "019ee484-uc6-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_use_case7_verifier_accepts_codex_structural_metadata(self) -> None:
        metadata = {
            "use_case": "use-case-7",
            "client": "codex",
            "session_id": "019ee484-uc7-codex",
            "container": "cf-uc7-codex-runner",
            "semantic_acceptance": "requires_agent_evaluation",
            "runner_contract": {
                "non_ephemeral_container": True,
                "reset_home_volume_requested": True,
                "virgin_workspace_reset_requested": True,
                "deterministic_checks_are_structural_only": True,
                "reset_client": "codex-cli",
            },
            "reset_json": {
                "ok": True,
                "client": "codex-cli",
                "client_reset": {"postcondition": True},
                "workspace_reset": {"postcondition": True},
            },
            "generation_report": {
                "model_dependent": True,
                "client": "codex",
                "session_id": "019ee484-uc7-codex",
                "step_generations": [
                    {
                        "turn": 1,
                        "model_dependent": True,
                        "returncode": 0,
                        "timeout": False,
                    }
                ],
                "totals": {
                    "prompt_count": 1,
                    "generation_step_count": 1,
                },
            },
            "commands": [
                {"command_text": "reset", "cwd": str(ROOT), "returncode": 0, "timeout": False},
                {"command_text": "turn", "cwd": str(ROOT), "returncode": 0, "timeout": False},
            ],
            "required_command_statuses": {
                "setup": {"returncode": 0, "timeout": False},
                "launch": {"returncode": 0, "timeout": False},
                "runtime": {"returncode": 0, "timeout": False},
                "fixture": {"returncode": 0, "timeout": False},
                "turn": {"returncode": 0, "timeout": False},
            },
            "semantic_criteria": [
                "natural_user_prompts",
                "project_state_readback_honesty",
                "hidden_instruction_boundary",
                "non_actions",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evidence = tmp_path / "codex-uc7.md"
            metadata_path = tmp_path / "codex-uc7-metadata.json"
            evidence.write_text("non-empty UC7 Codex evidence; semantic meaning is evaluator-owned", encoding="utf-8")
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(UC7_VERIFIER),
                    "--client",
                    "codex",
                    "--evidence",
                    str(evidence),
                    "--metadata",
                    str(metadata_path),
                    "--session-id",
                    "019ee484-uc7-codex",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["requires_agent_evaluation"])

    def test_method_document_separates_deterministic_and_semantic_work(self) -> None:
        text = METHOD_DOC.read_text(encoding="utf-8")

        self.assertIn("stepwise and total generation report", text)
        self.assertIn("Deterministic evaluation of generative outputs is disallowed", text)
        self.assertIn("declared structured artifact", text)
        self.assertIn("non-deterministic agent evaluation", text)

    def test_dialogue_method_records_visible_placeholder_quality_guard(self) -> None:
        text = METHOD_DOC.read_text(encoding="utf-8")
        collapsed = " ".join(text.split())

        self.assertIn("placeholder-only visible prefaces", text)
        self.assertIn("visible dialogue quality risks", text)
        self.assertIn("semantic evaluator judgments", collapsed)
        self.assertIn("must not decide that a free-form reply", collapsed)
        self.assertIn("by matching strings, regexes, ellipses", collapsed)

    def test_relevant_skills_share_structure_not_meaning_boundary(self) -> None:
        for path in [CONTROL_PLANE_SKILL, CONTROL_PLANE_EVIDENCE, DISPATCH_CARD]:
            text = path.read_text(encoding="utf-8")
            collapsed = " ".join(text.split())
            self.assertIn("matched strings", text, path)
            self.assertIn("regexes", text, path)
            self.assertIn("keyword", text, path)
            self.assertIn("string parsing", collapsed, path)
            self.assertIn("non-deterministic evaluator", collapsed, path)

    def test_use_case14_readiness_package_runner_and_verifier_define_claim_ladder(self) -> None:
        package = (ROOT / "docs" / "use-cases" / "use-case-14" / "package.md").read_text(encoding="utf-8")
        runner = (ROOT / "docker" / "client-harness" / "scripts" / "run-use-case-14-readiness-report.py").read_text(encoding="utf-8")
        verifier = (ROOT / "docker" / "client-harness" / "scripts" / "verify-use-case-14-readiness-evidence.py").read_text(encoding="utf-8")

        self.assertIn("Issue: #256", package)
        self.assertIn("Pi, OpenCode, and Codex", package)
        self.assertIn("claim ladder", package)
        self.assertIn("must not use matched strings, regexes, keyword searches", package)
        self.assertIn("semantic_report_review_required", runner)
        self.assertIn("build_acceptance_groups", runner)
        self.assertIn("safe_call_proof", runner)
        self.assertIn("handoff_readiness", runner)
        self.assertIn("forbidden_overclaims", runner)
        self.assertIn("REQUIRED_CLIENTS", verifier)
        self.assertIn("REQUIRED_LAYERS", verifier)
        self.assertIn("acceptance_groups", verifier)
        self.assertIn("does not judge report prose meaning", verifier)

    def test_use_case15_handoff_package_runner_and_verifier_define_handoff_boundary(self) -> None:
        package = (ROOT / "docs" / "use-cases" / "use-case-15" / "package.md").read_text(encoding="utf-8")
        runner = (ROOT / "docker" / "client-harness" / "scripts" / "run-use-case-15-handoff.py").read_text(encoding="utf-8")
        verifier = (ROOT / "docker" / "client-harness" / "scripts" / "verify-use-case-15-handoff-evidence.py").read_text(encoding="utf-8")

        self.assertIn("Issue: #257", package)
        self.assertIn("Pi, OpenCode, and Codex", package)
        self.assertIn("issue owns each gap", package)
        self.assertIn("semantic_handoff_review_required", runner)
        self.assertIn("client_operating_notes", runner)
        self.assertIn("validated_flows", runner)
        self.assertIn("read_issue_statuses", runner)
        self.assertIn("issue_owners", runner)
        self.assertIn("not release readiness", runner)
        self.assertIn("REQUIRED_CLIENTS", verifier)
        self.assertIn("REQUIRED_ISSUES", verifier)
        self.assertIn("what_works", verifier)
        self.assertIn("validated_flows", verifier)
        self.assertIn("does not judge handoff prose meaning", verifier)


if __name__ == "__main__":
    unittest.main()
