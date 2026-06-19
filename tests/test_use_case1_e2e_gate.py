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
        self.assertIn("Repeat testing -> remediation -> testing until both clients pass", text)
        self.assertIn("This is a loop, not a one-shot checklist", text)
        self.assertIn("Human testing is an acceptance check after", text)
        self.assertIn("one continuous command-line agent session with a stable", text)
        self.assertIn("scripts/verify-use-case-1-e2e-evidence.py", text)
        self.assertIn("The OpenCode gate fails if the agent calls record-validation before the safe", text)
        self.assertIn("Pi validation must", text)
        self.assertIn("go through the Pi-visible ContextForge shim/tool surface", text)

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

        self.assertEqual(0, code, result)
        self.assertTrue(result["ok"])

    def test_pi_rejects_shell_substitutes_and_missing_shim_validation(self) -> None:
        transcript = """
Session ID: pi-session
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

    def test_pi_accepts_clean_shim_validation(self) -> None:
        transcript = """
Session ID: pi-clean
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


if __name__ == "__main__":
    unittest.main()
