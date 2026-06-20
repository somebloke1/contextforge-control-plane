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
            },
            "reset_json": {
                "ok": True,
                "client": client,
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

        self.assertIn("build_structural_metadata", runner_text)
        self.assertIn("--metadata", runner_text)
        self.assertIn("deterministic_checks_are_structural_only", runner_text)
        self.assertIn("semantic_acceptance", runner_text)
        self.assertIn("verify_dialogue_structure", verifier_text)
        self.assertIn("check_generation_report", verifier_text)
        self.assertIn("semantic_criteria_for", verifier_text)
        self.assertNotIn("import re", verifier_text)

    def test_method_document_separates_deterministic_and_semantic_work(self) -> None:
        text = METHOD_DOC.read_text(encoding="utf-8")

        self.assertIn("stepwise and total generation report", text)
        self.assertIn("Deterministic evaluation of generative outputs is disallowed", text)
        self.assertIn("declared structured artifact", text)
        self.assertIn("non-deterministic agent evaluation", text)

    def test_relevant_skills_share_structure_not_meaning_boundary(self) -> None:
        for path in [CONTROL_PLANE_SKILL, CONTROL_PLANE_EVIDENCE, DISPATCH_CARD]:
            text = path.read_text(encoding="utf-8")
            collapsed = " ".join(text.split())
            self.assertIn("matched strings", text, path)
            self.assertIn("regexes", text, path)
            self.assertIn("keyword", text, path)
            self.assertIn("string parsing", collapsed, path)
            self.assertIn("non-deterministic evaluator", collapsed, path)


if __name__ == "__main__":
    unittest.main()
