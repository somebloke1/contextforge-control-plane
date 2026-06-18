from __future__ import annotations

import unittest
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import control_plane_contextforge_binding as binding
import project_init_common as common

DOC = ROOT / "docs/safe-client-visible-validation-probes.md"
OPEN_QUESTIONS = ROOT / "OPEN_QUESTIONS.md"
MATRIX = ROOT / "docs/client-visible-activation-matrix.md"
PI_SHIM = ROOT / "pi-extensions/contextforge-global-shim/index.ts"


class SafeClientVisibleValidationProbeCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.normalized = " ".join(cls.doc.split())
        cls.normalized_lower = cls.normalized.lower()

    def test_catalog_links_issue_and_open_question(self) -> None:
        self.assertIn("Issue: #97", self.doc)
        self.assertIn("Open question: `oq-20260531-0001`", self.doc)
        self.assertIn("safe default probe payload", OPEN_QUESTIONS.read_text(encoding="utf-8"))
        self.assertIn("docs/safe-client-visible-validation-probes.md", MATRIX.read_text(encoding="utf-8"))

    def test_catalog_distinguishes_client_surfaces(self) -> None:
        for phrase in [
            "Codex-visible MCP list/call proof",
            "Pi-visible shim/helper/guidance",
            "OpenCode-visible plugin/helper/MCP behavior",
            "Host Pi extension/shim readback",
            "direct backend checks",
            "Codex hook banners",
            "Pi client Docker evidence or source fixture evidence alone",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)
        self.assertIn("not sufficient", self.normalized_lower)

    def test_catalog_classifies_known_safe_probes(self) -> None:
        for service in ["context7", "mentality", "ssh-tmux"]:
            with self.subTest(service=service):
                self.assertIn(service, self.doc)

        for phrase in [
            "`known_safe_probe`",
            "small read-only documentation lookup",
            "Target-client list/read proof for governance records only",
            "Target-client list-sessions or session metadata readback only",
            "Decision writes",
            "Opening sessions",
            "sending commands",
            "shell process mutation",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_context7_probe_contract_is_documented_and_machine_readable(self) -> None:
        for phrase in [
            "## Context7 Probe Contract",
            "target-client `list-tools` evidence plus one",
            "context7-local-resolve-library-id",
            "context7-local-query-docs",
            '{"libraryName": "python"}',
            "target_client_safe_probe_result",
            "pi_safe_probe_result",
            "safe_probe_result: passed",
            "safe_probe_id: resolve-library-id",
            "direct Upstash/Context7 backend calls",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

        policy = common.safe_validation_policy("context7")
        contract = policy["probe_contract"]

        self.assertEqual("known_safe_probe", contract["status"])
        self.assertEqual(["list_tools", "call_tool"], contract["target_client_proof_layers"])
        self.assertEqual(
            ["context7-local-resolve-library-id", "context7-local-query-docs"],
            contract["allowed_tool_name_patterns"],
        )
        self.assertEqual("resolve-library-id", contract["default_probe"]["safe_probe_id"])
        self.assertEqual({"libraryName": "python"}, contract["default_probe"]["arguments"])
        self.assertEqual(
            {"target_client_safe_probe_result", "pi_safe_probe_result"},
            set(contract["accepted_proof_kinds"]),
        )
        self.assertEqual("passed", contract["validation_result_shape"]["status"])
        self.assertIs(contract["validation_result_shape"]["target_client_visible"], True)
        self.assertIn("backend health", contract["forbidden_substitutions"])
        self.assertIn("direct bridge call", contract["forbidden_substitutions"])

    def test_context7_probe_contract_flows_into_validation_plan(self) -> None:
        service = {
            "service_family": "context7",
            "service_binding": "context7:canonical",
            "validation_policy": common.safe_validation_policy("context7"),
        }
        plan = binding.build_project_init_validation_plan(
            [service],
            validation_mode="validate_now",
            target_client="codex",
        )
        service_plan = plan["service_plans"][0]
        safe_default = service_plan["safe_default"]

        self.assertEqual("target_client_visible_mcp", service_plan["required_proof"])
        self.assertEqual("pending_target_client_probe", service_plan["status"])
        self.assertEqual("safe_call", safe_default["mode"])
        self.assertEqual(
            ["resolve-library-id", "query-docs"],
            safe_default["safe_operations"],
        )
        self.assertEqual(
            "context7-local-resolve-library-id",
            safe_default["probe_contract"]["default_probe"]["tool_name_hint"],
        )
        self.assertEqual(
            "target_client_safe_probe_result",
            safe_default["probe_contract"]["validation_result_shape"]["proof_kind"],
        )

    def test_pi_shim_context7_defaults_align_with_probe_contract(self) -> None:
        text = PI_SHIM.read_text(encoding="utf-8")
        policy = common.safe_validation_policy("context7")

        for operation in policy["safe_operations"]:
            with self.subTest(operation=operation):
                self.assertIn(operation, text)

        self.assertIn('proof_kind: "pi_safe_probe_result"', text)
        self.assertIn("safe_probe_result", text)
        self.assertIn("safeProbeId", text)

    def test_catalog_classifies_conditional_and_skipped_probes(self) -> None:
        for service in [
            "OpenZeppelin Solidity Contracts",
            "web-search",
            "Exa Search",
            "GitHub",
            "Playwright",
            "Serena/project-scoped services",
            "Pi/OpenCode activation helpers",
            "Any unlisted service",
        ]:
            with self.subTest(service=service):
                self.assertIn(service, self.doc)

        for phrase in [
            "`conditional_probe`",
            "`skip_until_probe_exists`",
            "credentials, cost, environment, target resource, or side effects",
            "credential scope confirmed",
            "controlled fixture page",
            "must remain skipped or presumed-working",
            "another service's probe",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_claim_rules_preserve_no_fake_validation_policy(self) -> None:
        for phrase in [
            "Record `validated` only after the exact target client lists",
            "Record `skipped` when no safe payload exists",
            "Record `presumed_working` only when the operator explicitly chooses that state",
            "no target-client proof is claimed",
            "Keep credentials, bearer tokens, OAuth state, trust tokens",
            "one service, one client surface, one safe payload",
            "does not approve live runtime/client validation",
            ".project/context_forge_state.json",
            "retired legacy checkout mutation",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)


if __name__ == "__main__":
    unittest.main()
