from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "docker/client-harness/scripts/verify-use-case-1-e2e-evidence.py"
GATE_DOC = ROOT / "docker/client-harness/USE_CASE_1_E2E_GATE.md"
DIALOGUE_SKILL = ROOT / ".codex/skills/code-assistant-dialogue-validation/SKILL.md"


class UseCase1E2EGateTests(unittest.TestCase):
    def run_verifier(self, client: str, text: str, *extra: str) -> tuple[int, dict[str, object]]:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / f"{client}.md"
            evidence.write_text(text, encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(VERIFIER), "--client", client, "--evidence", str(evidence), *extra],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        self.assertEqual("", completed.stderr)
        return completed.returncode, json.loads(completed.stdout)

    def test_gate_document_requires_agent_e2e_before_human_validation(self) -> None:
        text = GATE_DOC.read_text(encoding="utf-8")

        self.assertIn("Human validation must not be requested until this gate has passed", text)
        self.assertIn("code-assistant-dialogue-validation", text)
        self.assertIn("Delegate a Pi dialogue-validation lease to a dev agent", text)
        self.assertIn("Delegate an OpenCode dialogue-validation lease to a dev agent", text)
        self.assertIn("non-ephemeral Pi harness", text)
        self.assertIn("non-ephemeral OpenCode", text)
        self.assertIn("remove stale containers only for the client type being", text)
        self.assertIn("wait at least 90 seconds", text)
        self.assertIn("Container cleanup is not volume or workspace cleanup", text)
        self.assertIn("Canonical Pi Prompt Sequence", text)
        self.assertIn("presumed-working", text)
        self.assertIn("No truncated use-case test stories are allowed", text)
        self.assertIn("full specified story", text)
        self.assertIn("Do not assign the", text)
        self.assertIn("full multi-turn Pi/OpenCode dialogue run to Spark", text)
        self.assertIn("must be a non-Spark model", text)
        self.assertIn("Raw client JSON streams can be large", text)
        self.assertIn("targeted readbacks", text)
        self.assertIn("not permission to truncate the story", text)
        self.assertIn("Do not invert deterministic and semantic responsibilities", text)
        self.assertIn("must be scripted/idempotent", text)
        self.assertIn("high-dimensional semantic work", text)
        self.assertIn("pattern matching or residue-delta inference", text)
        self.assertIn("docker/client-harness/scripts/reset-client-harness-state.py", text)
        self.assertIn("--client <pi|opencode> --reset-home-volume", text)
        self.assertIn("fixed JSON postcondition readback", text)
        self.assertIn("Each validation attempt starts from a virgin test workspace", text)
        self.assertIn("idempotent reset", text)
        self.assertIn("converge on the same clean postcondition", text)
        self.assertIn("depends on a person or agent deciding which", text)
        self.assertIn("There is no validation value in carrying", text)
        self.assertIn("workspace cleanup or reset command", text)
        self.assertIn("Repeat testing -> remediation -> testing until both clients pass", text)
        self.assertIn("This is a loop, not a one-shot checklist", text)
        self.assertIn("Human testing is an acceptance check after", text)
        self.assertIn("The verifier is an audit gate, not the validation actor", text)
        self.assertIn("one continuous command-line agent session with a stable", text)
        self.assertIn("scripts/verify-use-case-1-e2e-evidence.py", text)
        self.assertIn("The OpenCode gate fails if the agent calls record-validation before the safe", text)
        self.assertIn("Pi validation must", text)
        self.assertIn("go through the Pi-visible ContextForge shim/tool surface", text)
        self.assertIn("Record only the reload acknowledgement", text)
        self.assertIn("do not pass validationMode", text)
        self.assertIn("without `cf_contextforge_pi_validate` appearing as an observed tool", text)
        self.assertIn("interruption-safe checkpoint", text)
        self.assertIn("interruption-incomplete", text)
        self.assertIn("targeted readbacks for every live challenge id", text)

    def test_dialogue_validation_skill_defines_delegated_agent_contract(self) -> None:
        text = DIALOGUE_SKILL.read_text(encoding="utf-8")

        self.assertIn("name: code-assistant-dialogue-validation", text)
        self.assertIn("A scripted smoke test can prepare the environment or audit captured evidence.", text)
        self.assertIn("It cannot satisfy a human-facing dialogue gate.", text)
        self.assertIn("validator agent conducting the same interaction a human would conduct", text)
        self.assertIn("Deterministic setup belongs", text)
        self.assertIn("Do not ask a language model to infer which", text)
        self.assertIn("Reserve the delegated language model for the semantic work", text)
        self.assertIn("reset-client-harness-state.py", text)
        self.assertIn("Validator leases should cite this script", text)
        self.assertIn("non-ephemeral Compose service", text)
        self.assertIn("Do not use `--rm`", text)
        self.assertIn("wait at least 90 seconds", text)
        self.assertIn("Do not prune unrelated", text)
        self.assertIn("preserve the raw tool events", text)
        self.assertIn("No truncated use-case test stories are allowed", text)
        self.assertIn("full specified story", text)
        self.assertIn("Spark work unit", text)
        self.assertIn("must not own a multi-turn LM-engaging", text)
        self.assertIn("Preserve the raw stream", text)
        self.assertIn("use targeted readbacks", text)
        self.assertIn("do not replace live readback with pattern guesses", text)
        self.assertIn("virgin per-test harness workspace cleanup", text)
        self.assertIn("idempotent target-client reset operation", text)
        self.assertIn("fixed postcondition", text)
        self.assertIn("safe to run repeatedly", text)
        self.assertIn("Persistence is required only inside the single validation run", text)
        self.assertIn("stable session id", text)
        self.assertIn("target-client validation uses the actual visible ContextForge tool", text)
        self.assertIn("no helper rejection is needed to teach the required sequence", text)
        self.assertIn("reload acknowledgement as its own narrow action", text)
        self.assertIn("Do not pass `validationMode`", text)
        self.assertIn("The observed tool index must be built from real tool-call events", text)
        self.assertIn("complete-until-observed stop rule", text)
        self.assertIn("interruption-safe checkpoint", text)

    def test_opencode_rejects_record_validation_before_safe_probe(self) -> None:
        transcript = """
# Validate ContextForge services
Session ID: ses_1214
Assistant (Build - Qwen 3.6 A3B via host llama.cpp)
Tool: contextforge-helper_cf_project_init_get_context
Output: {"project_root": "/workspace"}
Tool: contextforge-helper_cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded_validation_requested"}
Tool: contextforge-helper_cf_project_init_record_validation
Input: {"target_client": "opencode"}
Output: {"status":"validation_results_insufficient"}
Tool: context7_context7-local-resolve-library-id
Output: Available Libraries
Tool: contextforge-helper_cf_project_init_record_validation
Output: {"status":"validation_recorded","project_status":"initialized"}
"""
        code, result = self.run_verifier("opencode", transcript)

        self.assertNotEqual(0, code)
        failure_codes = {failure["code"] for failure in result["failures"]}  # type: ignore[index]
        self.assertIn("record_validation_before_safe_probe", failure_codes)
        self.assertIn("validation_results_insufficient", failure_codes)

    def test_opencode_accepts_clean_safe_probe_then_record_validation(self) -> None:
        transcript = """
# Validate ContextForge services
Session ID: ses_clean
Command: docker compose -f docker/client-harness/compose.yml rm -sf opencode opencode-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --name cf-opencode-uc1 opencode bash
Assistant (Build - Qwen 3.6 A3B via host llama.cpp)
Tool: contextforge-helper_cf_project_init_get_context
Output: {"project_root": "/workspace", "service": "context7:canonical"}
Tool: contextforge-helper_cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded_validation_requested"}
Tool: context7_context7-local-resolve-library-id
Output: Available Libraries
Tool: contextforge-helper_cf_project_init_record_validation
Input: {"validation_results":{"context7:canonical":{"target_client": "opencode"}}}
Output: {"status":"validation_recorded","project_status":"initialized"}
Tool: contextforge-helper_get_project_context
Output: {"helper":{"status":"available"}}
"""
        code, result = self.run_verifier("opencode", transcript)

        self.assertEqual(0, code, result)
        self.assertTrue(result["ok"])

    def test_opencode_allows_presumed_working_option_text_without_action(self) -> None:
        transcript = """
# Validate ContextForge services
Session ID: ses_clean_options
Command: docker compose -f docker/client-harness/compose.yml rm -sf opencode opencode-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --name cf-opencode-uc1 opencode bash
Assistant (Build - Qwen 3.6 A3B via host llama.cpp)
Tool: contextforge-helper_cf_project_init_apply
Output: {"project_root": "/workspace", "next_turn":{"prompt":"choose 2 or reply skip validation to record presumed working without verification"}}
Tool: contextforge-helper_cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded_validation_requested"}
Tool: context7_context7-local-resolve-library-id
Output: Available Libraries
Tool: contextforge-helper_cf_project_init_record_validation
Input: {"validation_results":{"context7:canonical":{"target_client": "opencode"}}}
Output: {"status":"validation_recorded","project_status":"initialized"}
Tool: contextforge-helper_get_project_context
Output: {"helper":{"status":"available"}}
"""
        code, result = self.run_verifier("opencode", transcript)

        self.assertEqual(0, code, result)
        self.assertTrue(result["ok"])

    def test_opencode_rejects_actual_presumed_working_recording(self) -> None:
        transcript = """
# Validate ContextForge services
Session ID: ses_presumed
Command: docker compose -f docker/client-harness/compose.yml rm -sf opencode opencode-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --name cf-opencode-uc1 opencode bash
Assistant (Build - Qwen 3.6 A3B via host llama.cpp)
Tool: contextforge-helper_cf_project_init_record_client_reload
Input: {"validation_mode":"presume_working"}
Output: {"status":"client_reload_recorded_presume_working_requested"}
Tool: contextforge-helper_cf_project_init_record_validation
Input: {"validation_mode":"presume_working"}
Output: {"status":"validation_recorded","project_status":"in_progress"}
"""
        code, result = self.run_verifier("opencode", transcript)

        self.assertNotEqual(0, code)
        failure_codes = {failure["code"] for failure in result["failures"]}  # type: ignore[index]
        self.assertIn("presumed_working_validation", failure_codes)

    def test_opencode_rejects_ephemeral_container_launch(self) -> None:
        transcript = """
# Validate ContextForge services
Session ID: ses_ephemeral
Command: docker compose -f docker/client-harness/compose.yml rm -sf opencode opencode-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --rm --no-deps opencode-ephemeral bash
Assistant (Build - Qwen 3.6 A3B via host llama.cpp)
Tool: contextforge-helper_cf_project_init_get_context
Output: {"project_root": "/workspace", "service": "context7:canonical"}
Tool: contextforge-helper_cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded_validation_requested"}
Tool: context7_context7-local-resolve-library-id
Output: Available Libraries
Tool: contextforge-helper_cf_project_init_record_validation
Input: {"validation_results":{"context7:canonical":{"target_client": "opencode"}}}
Output: {"status":"validation_recorded","project_status":"initialized"}
"""
        code, result = self.run_verifier("opencode", transcript)

        self.assertNotEqual(0, code)
        failure_codes = {failure["code"] for failure in result["failures"]}  # type: ignore[index]
        self.assertIn("ephemeral_container_launch", failure_codes)
        self.assertIn("missing_non_ephemeral_container_launch", failure_codes)

    def test_pi_rejects_shell_substitutes_and_missing_shim_validation(self) -> None:
        transcript = """
Session ID: pi-session
Command: docker compose -f docker/client-harness/compose.yml rm -sf pi pi-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --name cf-pi-uc1 pi bash
Build - qwen3.6-a3b
projectRoot /workspace context7:canonical
cf_project_init_record_client_reload
$ python3 -m context7_local_resolve_library_id
No module named context7_local_resolve_library_id
$ npx -y @upstash/context7-mcp@latest --transport stdio
ContextForge initialization is complete but validation couldn't run.
"""
        code, result = self.run_verifier("pi", transcript)

        self.assertNotEqual(0, code)
        failure_codes = {failure["code"] for failure in result["failures"]}  # type: ignore[index]
        self.assertIn("pi_validate_tool_called", failure_codes)
        self.assertIn("python_context7_module_substitute", failure_codes)
        self.assertIn("npx_context7_backend_substitute", failure_codes)
        self.assertIn("validation_could_not_run", failure_codes)

    def test_pi_rejects_presumed_working_validation(self) -> None:
        transcript = """
Session ID: pi-presume
Command: docker compose -f docker/client-harness/compose.yml rm -sf pi pi-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --name cf-pi-uc1 pi bash
Build - qwen3.6-a3b
projectRoot /workspace context7:canonical
Tool: cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded"}
Assistant: I will record validation as presumed-working.
Tool: cf_project_init_record_validation
Output: {"status":"validation_recorded","project_status":"initialized"}
"""
        code, result = self.run_verifier("pi", transcript)

        self.assertNotEqual(0, code)
        failure_codes = {failure["code"] for failure in result["failures"]}  # type: ignore[index]
        self.assertIn("presumed_working_validation", failure_codes)
        self.assertIn("pi_validate_tool_called", failure_codes)

    def test_pi_accepts_clean_shim_validation(self) -> None:
        transcript = """
Session ID: pi-clean
Command: docker compose -f docker/client-harness/compose.yml rm -sf pi pi-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --name cf-pi-uc1 pi bash
Build - qwen3.6-a3b
projectRoot /workspace context7:canonical
Tool: cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded"}
Tool: cf_contextforge_pi_validate
Output: {"status":"pi_validation_complete","summary":{"passed":1}}
Tool: cf_project_init_record_validation
Output: {"status":"validation_recorded","project_status":"initialized"}
"""
        code, result = self.run_verifier("pi", transcript)

        self.assertEqual(0, code, result)
        self.assertTrue(result["ok"])

    def test_pi_accepts_reset_script_cleanup_evidence(self) -> None:
        transcript = """
Session ID: pi-reset-clean
Command: PYTHONDONTWRITEBYTECODE=1 python3 docker/client-harness/scripts/reset-client-harness-state.py --client pi --reset-home-volume
Output: {
  "client": "pi",
  "client_reset": {
    "postcondition": true,
    "remaining_target_volume_containers": []
  },
  "workspace_reset": {
    "postcondition": true,
    "entries": [".gitkeep"]
  }
}
Command: docker compose -f docker/client-harness/compose.yml run --name cf-pi-uc1 pi bash
Build - qwen3.6-a3b
projectRoot /workspace context7:canonical
Tool: cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded"}
Tool: cf_contextforge_pi_validate
Output: {"status":"pi_validation_complete","summary":{"passed":1}}
Tool: cf_project_init_record_validation
Output: {"status":"validation_recorded","project_status":"initialized"}
"""
        code, result = self.run_verifier("pi", transcript)

        self.assertEqual(0, code, result)
        self.assertTrue(result["checks"]["client_stale_container_cleanup"])  # type: ignore[index]

    def test_pi_accepts_controller_reported_reset_postcondition_evidence(self) -> None:
        transcript = """
Session ID: pi-reset-summary
Controller reset command already completed before this validator run:
PYTHONDONTWRITEBYTECODE=1 python3 docker/client-harness/scripts/reset-client-harness-state.py --client pi --reset-home-volume
Controller-reported result: ok=true; client_reset.postcondition=true; workspace_reset.postcondition=true; workspace entries allowlist [.gitkeep]; remaining_target_volume_containers=[].
Readback command: find docker/client-harness/workspace -maxdepth 3 -mindepth 1 -print | sort
Output: docker/client-harness/workspace/.gitkeep
Command: docker compose -f docker/client-harness/compose.yml run --name cf-pi-uc1 pi sleep infinity
Build - qwen3.6-a3b
projectRoot /workspace context7:canonical
Tool: cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded"}
Tool: cf_contextforge_pi_validate
Output: {"status":"pi_validation_complete","summary":{"passed":1}}
Tool: cf_project_init_record_validation
Output: {"status":"validation_recorded","project_status":"initialized"}
"""
        code, result = self.run_verifier("pi", transcript)

        self.assertEqual(0, code, result)
        self.assertTrue(result["checks"]["client_stale_container_cleanup"])  # type: ignore[index]

    def test_pi_rejects_prose_only_validate_mention(self) -> None:
        transcript = """
Session ID: pi-prose-only
Command: docker compose -f docker/client-harness/compose.yml rm -sf pi pi-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --name cf-pi-uc1 pi bash
Build - qwen3.6-a3b
projectRoot /workspace context7:canonical
Tool: cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded"}
Assistant: I will invoke cf_contextforge_pi_validate next.
Tool: cf_project_init_record_validation
Output: {"status":"validation_recorded","project_status":"initialized"}
"""
        code, result = self.run_verifier("pi", transcript)

        self.assertNotEqual(0, code)
        failure_codes = {failure["code"] for failure in result["failures"]}  # type: ignore[index]
        self.assertIn("pi_validate_tool_called", failure_codes)
        self.assertIn("pi_record_validation_before_validate", failure_codes)

    def test_pi_rejects_record_validation_before_validate_tool_call(self) -> None:
        transcript = """
Session ID: pi-wrong-order
Command: docker compose -f docker/client-harness/compose.yml rm -sf pi pi-ephemeral
Command: docker compose -f docker/client-harness/compose.yml run --name cf-pi-uc1 pi bash
Build - qwen3.6-a3b
projectRoot /workspace context7:canonical
Tool: cf_project_init_record_client_reload
Output: {"status":"client_reload_recorded"}
Tool: cf_project_init_record_validation
Output: {"status":"validation_recorded","project_status":"initialized"}
Tool: cf_contextforge_pi_validate
Output: {"status":"pi_validation_complete","summary":{"passed":1}}
"""
        code, result = self.run_verifier("pi", transcript)

        self.assertNotEqual(0, code)
        failure_codes = {failure["code"] for failure in result["failures"]}  # type: ignore[index]
        self.assertIn("pi_record_validation_before_validate", failure_codes)


if __name__ == "__main__":
    unittest.main()
