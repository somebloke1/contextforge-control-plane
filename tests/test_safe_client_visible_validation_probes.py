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
                self.assertIn(phrase, self.normalized)

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
                self.assertIn(phrase, self.normalized)

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

    def test_mentality_probe_contract_is_documented_and_machine_readable(self) -> None:
        for phrase in [
            "## Mentality Probe Contract",
            "target-client `list-tools` evidence plus one",
            "mentality-governance-list",
            "mentality-governance-read",
            "governance_list",
            "governance_read",
            '{"repo": "PROJECT_ROOT", "ledger": "decisions"}',
            "target_client_safe_probe_result",
            "pi_safe_probe_result",
            "safe_probe_result: passed",
            "safe_probe_id: governance-list",
            "governance create",
            "governance update",
            "governance delete",
            "local ledger file reads",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

        policy = common.safe_validation_policy("mentality")
        contract = policy["probe_contract"]

        self.assertEqual("known_safe_probe", contract["status"])
        self.assertEqual(["list_tools", "call_tool"], contract["target_client_proof_layers"])
        self.assertEqual(
            [
                "mentality-governance-list",
                "mentality-governance-read",
                "governance_list",
                "governance_read",
            ],
            contract["allowed_tool_name_patterns"],
        )
        self.assertEqual("governance-list", contract["default_probe"]["safe_probe_id"])
        self.assertEqual(
            {"repo": "PROJECT_ROOT", "ledger": "decisions"},
            contract["default_probe"]["arguments"],
        )
        self.assertEqual(
            {"target_client_safe_probe_result", "pi_safe_probe_result"},
            set(contract["accepted_proof_kinds"]),
        )
        self.assertEqual("passed", contract["validation_result_shape"]["status"])
        self.assertIs(contract["validation_result_shape"]["target_client_visible"], True)
        self.assertIn("governance create", contract["forbidden_substitutions"])
        self.assertIn("local ledger file read", contract["forbidden_substitutions"])

    def test_mentality_probe_contract_flows_into_validation_plan(self) -> None:
        service = {
            "service_family": "mentality",
            "service_binding": "mentality:static_repo_local",
            "validation_policy": common.safe_validation_policy("mentality"),
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
        self.assertEqual("read_only", safe_default["mode"])
        self.assertEqual(
            ["governance-list", "governance-read"],
            safe_default["safe_operations"],
        )
        self.assertEqual(
            "mentality-governance-list",
            safe_default["probe_contract"]["default_probe"]["tool_name_hint"],
        )
        self.assertEqual(
            "target_client_safe_probe_result",
            safe_default["probe_contract"]["validation_result_shape"]["proof_kind"],
        )

    def test_context7_result_builder_boundary_is_documented(self) -> None:
        for phrase in [
            "## Context7 Result Builder Boundary",
            "Issue #101",
            "shaping contract only",
            "does not call Context7",
            "Wrong tools, unsupported proof kinds, missing target-client trace refs",
            "non-passing result instead of a validation claim",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_context7_result_builder_accepts_target_client_safe_proof(self) -> None:
        result = common.build_safe_probe_validation_result(
            "context7",
            target_client="codex",
            tool_name="context7-local-resolve-library-id",
            verification_trace_refs=["contextforge://control-plane/traces/context7-target-client"],
            result_summary="resolved /python/cpython",
        )

        self.assertEqual("passed", result["status"])
        self.assertIs(result["target_client_visible"], True)
        self.assertEqual("target_client_safe_probe_result", result["proof_kind"])
        self.assertEqual("passed", result["safe_probe_result"])
        self.assertEqual("resolve-library-id", result["safe_probe_id"])
        self.assertEqual("codex", result["target_client"])
        self.assertEqual("context7-local-resolve-library-id", result["tool_name"])
        self.assertEqual(
            ["contextforge://control-plane/traces/context7-target-client"],
            result["verification_trace_refs"],
        )

    def test_context7_result_builder_accepts_pi_safe_proof_kind(self) -> None:
        result = common.build_safe_probe_validation_result(
            "context7",
            target_client="pi",
            tool_name="cf_context7_s123__context7-local-resolve-library-id",
            verification_trace_refs=[
                "pi://contextforge-global-shim/tools/cf_context7_s123__context7-local-resolve-library-id"
            ],
            proof_kind="pi_safe_probe_result",
        )

        self.assertEqual("passed", result["status"])
        self.assertIs(result["target_client_visible"], True)
        self.assertEqual("pi_safe_probe_result", result["proof_kind"])

    def test_context7_result_builder_rejects_non_target_client_substitutes(self) -> None:
        cases = [
            (
                "wrong_tool",
                {
                    "tool_name": "local-package-lookup",
                    "verification_trace_refs": ["contextforge://control-plane/traces/context7-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "unsupported_proof",
                {
                    "tool_name": "context7-local-resolve-library-id",
                    "proof_kind": "backend_health",
                    "verification_trace_refs": ["contextforge://control-plane/traces/context7-target-client"],
                },
                "unsupported_proof_kind",
            ),
            (
                "missing_trace",
                {
                    "tool_name": "context7-local-resolve-library-id",
                    "verification_trace_refs": [],
                },
                "missing_target_client_trace",
            ),
            (
                "failed_probe",
                {
                    "tool_name": "context7-local-resolve-library-id",
                    "safe_probe_result": "error",
                    "status": "pending",
                    "verification_trace_refs": ["contextforge://control-plane/traces/context7-target-client"],
                },
                "safe_probe_not_passed",
            ),
        ]

        for name, kwargs, reason in cases:
            with self.subTest(name=name):
                result = common.build_safe_probe_validation_result(
                    "context7",
                    target_client="codex",
                    **kwargs,
                )
                self.assertEqual("pending", result["status"])
                self.assertIs(result["target_client_visible"], False)
                self.assertEqual(reason, result["skipped_reason"])

    def test_mentality_result_builder_accepts_target_client_safe_proof(self) -> None:
        result = common.build_safe_probe_validation_result(
            "mentality",
            target_client="codex",
            tool_name="mentality-governance-list",
            verification_trace_refs=["contextforge://control-plane/traces/mentality-target-client"],
            result_summary="listed governance entries",
        )

        self.assertEqual("passed", result["status"])
        self.assertIs(result["target_client_visible"], True)
        self.assertEqual("target_client_safe_probe_result", result["proof_kind"])
        self.assertEqual("passed", result["safe_probe_result"])
        self.assertEqual("governance-list", result["safe_probe_id"])
        self.assertEqual("codex", result["target_client"])
        self.assertEqual("mentality-governance-list", result["tool_name"])
        self.assertEqual(
            ["contextforge://control-plane/traces/mentality-target-client"],
            result["verification_trace_refs"],
        )

    def test_mentality_result_builder_rejects_mutating_or_local_substitutes(self) -> None:
        cases = [
            (
                "mutating_tool",
                {
                    "tool_name": "mentality-governance-create",
                    "verification_trace_refs": ["contextforge://control-plane/traces/mentality-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "local_file_read",
                {
                    "tool_name": "cat DECISIONS.md",
                    "verification_trace_refs": ["contextforge://control-plane/traces/mentality-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "unsupported_safe_probe",
                {
                    "tool_name": "mentality-governance-list",
                    "safe_probe_id": "governance-delete",
                    "verification_trace_refs": ["contextforge://control-plane/traces/mentality-target-client"],
                },
                "unsupported_safe_probe_id",
            ),
            (
                "missing_trace",
                {
                    "tool_name": "mentality-governance-list",
                    "verification_trace_refs": [],
                },
                "missing_target_client_trace",
            ),
            (
                "failed_probe",
                {
                    "tool_name": "mentality-governance-list",
                    "safe_probe_result": "error",
                    "status": "pending",
                    "verification_trace_refs": ["contextforge://control-plane/traces/mentality-target-client"],
                },
                "safe_probe_not_passed",
            ),
        ]

        for name, kwargs, reason in cases:
            with self.subTest(name=name):
                result = common.build_safe_probe_validation_result(
                    "mentality",
                    target_client="codex",
                    **kwargs,
                )
                self.assertEqual("pending", result["status"])
                self.assertIs(result["target_client_visible"], False)
                self.assertEqual(reason, result["skipped_reason"])

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
