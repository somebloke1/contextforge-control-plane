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
            '{"libraryName": "python", "query": "standard library documentation lookup"}',
            "requires both `libraryName` and `query`",
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
        self.assertEqual(
            {
                "libraryName": "python",
                "query": "standard library documentation lookup",
            },
            contract["default_probe"]["arguments"],
        )
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

    def test_ssh_tmux_probe_contract_is_documented_and_machine_readable(self) -> None:
        for phrase in [
            "## ssh-tmux Probe Contract",
            "target-client `list-tools` evidence plus one",
            "ssh-tmux-list-sessions",
            "ssh-tmux-get-snapshot",
            "list_sessions",
            "get_snapshot",
            "call `ssh-tmux-list-sessions` with `{}`",
            "target_client_safe_probe_result",
            "pi_safe_probe_result",
            "safe_probe_result: passed",
            "safe_probe_id: list-sessions",
            "opening sessions",
            "sending commands or keys",
            "cleanup/deletion",
            "direct shell or tmux commands",
            "local process inspection",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

        policy = common.safe_validation_policy("ssh-tmux")
        contract = policy["probe_contract"]

        self.assertEqual("known_safe_probe", contract["status"])
        self.assertEqual(["list_tools", "call_tool"], contract["target_client_proof_layers"])
        self.assertEqual(
            [
                "ssh-tmux-list-sessions",
                "ssh-tmux-get-snapshot",
                "list_sessions",
                "get_snapshot",
            ],
            contract["allowed_tool_name_patterns"],
        )
        self.assertEqual("list-sessions", contract["default_probe"]["safe_probe_id"])
        self.assertEqual({}, contract["default_probe"]["arguments"])
        self.assertEqual(
            {"target_client_safe_probe_result", "pi_safe_probe_result"},
            set(contract["accepted_proof_kinds"]),
        )
        self.assertEqual("passed", contract["validation_result_shape"]["status"])
        self.assertIs(contract["validation_result_shape"]["target_client_visible"], True)
        self.assertIn("send command", contract["forbidden_substitutions"])
        self.assertIn("direct shell or tmux command", contract["forbidden_substitutions"])
        self.assertIn("local process inspection", contract["forbidden_substitutions"])

    def test_ssh_tmux_probe_contract_flows_into_validation_plan(self) -> None:
        service = {
            "service_family": "ssh-tmux",
            "service_binding": "ssh-tmux:canonical",
            "validation_policy": common.safe_validation_policy("ssh-tmux"),
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
            ["list-sessions", "get-snapshot"],
            safe_default["safe_operations"],
        )
        self.assertEqual(
            "ssh-tmux-list-sessions",
            safe_default["probe_contract"]["default_probe"]["tool_name_hint"],
        )
        self.assertEqual(
            "target_client_safe_probe_result",
            safe_default["probe_contract"]["validation_result_shape"]["proof_kind"],
        )

    def test_openzeppelin_probe_contract_is_documented_and_machine_readable(self) -> None:
        for phrase in [
            "## OpenZeppelin Solidity Contracts Probe Contract",
            "target-client `list-tools` evidence plus one",
            "openzeppelin-solidity-contracts-solidity-erc20",
            "ContextForgePreviewToken",
            "symbol `CFP`",
            "premint `0`",
            "access `none`",
            "target_client_safe_probe_result",
            "pi_safe_probe_result",
            "safe_probe_result: passed",
            "safe_probe_id: solidity-erc20-preview",
            "remote OpenZeppelin availability",
            "generated code treated as audited",
            "wallet/private-key input",
            "chain/RPC interaction",
            "secret-bearing input",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

        policy = common.safe_validation_policy("openzeppelin-solidity-contracts")
        contract = policy["probe_contract"]

        self.assertEqual("known_safe_probe", contract["status"])
        self.assertEqual(["list_tools", "call_tool"], contract["target_client_proof_layers"])
        self.assertEqual(
            ["openzeppelin-solidity-contracts-solidity-erc20"],
            contract["allowed_tool_name_patterns"],
        )
        self.assertEqual("solidity-erc20-preview", contract["default_probe"]["safe_probe_id"])
        self.assertEqual(
            {
                "name": "ContextForgePreviewToken",
                "symbol": "CFP",
                "premint": "0",
                "mintable": False,
                "burnable": False,
                "pausable": False,
                "permit": False,
                "callback": False,
                "votes": False,
                "flashmint": False,
                "crossChainBridging": False,
                "access": "none",
                "upgradeable": False,
            },
            contract["default_probe"]["arguments"],
        )
        self.assertEqual(
            {"target_client_safe_probe_result", "pi_safe_probe_result"},
            set(contract["accepted_proof_kinds"]),
        )
        self.assertEqual("passed", contract["validation_result_shape"]["status"])
        self.assertIs(contract["validation_result_shape"]["target_client_visible"], True)
        self.assertIn("generated code audit claim", contract["forbidden_substitutions"])
        self.assertIn("wallet or private key", contract["forbidden_substitutions"])
        self.assertIn("chain or RPC interaction", contract["forbidden_substitutions"])

    def test_openzeppelin_probe_contract_flows_into_validation_plan(self) -> None:
        service = {
            "service_family": "openzeppelin-solidity-contracts",
            "service_binding": "openzeppelin-solidity-contracts:canonical",
            "validation_policy": common.safe_validation_policy("openzeppelin-solidity-contracts"),
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
            ["solidity-erc20-preview"],
            safe_default["safe_operations"],
        )
        self.assertEqual(
            "openzeppelin-solidity-contracts-solidity-erc20",
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

    def test_ssh_tmux_result_builder_accepts_target_client_safe_proof(self) -> None:
        result = common.build_safe_probe_validation_result(
            "ssh-tmux",
            target_client="codex",
            tool_name="ssh-tmux-list-sessions",
            verification_trace_refs=["contextforge://control-plane/traces/ssh-tmux-target-client"],
            result_summary="listed existing sessions",
        )

        self.assertEqual("passed", result["status"])
        self.assertIs(result["target_client_visible"], True)
        self.assertEqual("target_client_safe_probe_result", result["proof_kind"])
        self.assertEqual("passed", result["safe_probe_result"])
        self.assertEqual("list-sessions", result["safe_probe_id"])
        self.assertEqual("codex", result["target_client"])
        self.assertEqual("ssh-tmux-list-sessions", result["tool_name"])
        self.assertEqual(
            ["contextforge://control-plane/traces/ssh-tmux-target-client"],
            result["verification_trace_refs"],
        )

    def test_ssh_tmux_result_builder_rejects_mutating_or_local_substitutes(self) -> None:
        cases = [
            (
                "open_session",
                {
                    "tool_name": "ssh-tmux-open-session",
                    "verification_trace_refs": ["contextforge://control-plane/traces/ssh-tmux-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "send_command",
                {
                    "tool_name": "ssh-tmux-send-command",
                    "verification_trace_refs": ["contextforge://control-plane/traces/ssh-tmux-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "direct_shell",
                {
                    "tool_name": "tmux list-sessions",
                    "verification_trace_refs": ["contextforge://control-plane/traces/ssh-tmux-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "unsupported_safe_probe",
                {
                    "tool_name": "ssh-tmux-list-sessions",
                    "safe_probe_id": "send-command",
                    "verification_trace_refs": ["contextforge://control-plane/traces/ssh-tmux-target-client"],
                },
                "unsupported_safe_probe_id",
            ),
            (
                "missing_trace",
                {
                    "tool_name": "ssh-tmux-list-sessions",
                    "verification_trace_refs": [],
                },
                "missing_target_client_trace",
            ),
            (
                "failed_probe",
                {
                    "tool_name": "ssh-tmux-list-sessions",
                    "safe_probe_result": "error",
                    "status": "pending",
                    "verification_trace_refs": ["contextforge://control-plane/traces/ssh-tmux-target-client"],
                },
                "safe_probe_not_passed",
            ),
        ]

        for name, kwargs, reason in cases:
            with self.subTest(name=name):
                result = common.build_safe_probe_validation_result(
                    "ssh-tmux",
                    target_client="codex",
                    **kwargs,
                )
                self.assertEqual("pending", result["status"])
                self.assertIs(result["target_client_visible"], False)
                self.assertEqual(reason, result["skipped_reason"])

    def test_openzeppelin_result_builder_accepts_target_client_safe_proof(self) -> None:
        result = common.build_safe_probe_validation_result(
            "openzeppelin-solidity-contracts",
            target_client="codex",
            tool_name="openzeppelin-solidity-contracts-solidity-erc20",
            verification_trace_refs=["contextforge://control-plane/traces/openzeppelin-target-client"],
            result_summary="generated deterministic ERC-20 preview text",
        )

        self.assertEqual("passed", result["status"])
        self.assertIs(result["target_client_visible"], True)
        self.assertEqual("target_client_safe_probe_result", result["proof_kind"])
        self.assertEqual("passed", result["safe_probe_result"])
        self.assertEqual("solidity-erc20-preview", result["safe_probe_id"])
        self.assertEqual("codex", result["target_client"])
        self.assertEqual("openzeppelin-solidity-contracts-solidity-erc20", result["tool_name"])
        self.assertEqual(
            ["contextforge://control-plane/traces/openzeppelin-target-client"],
            result["verification_trace_refs"],
        )

    def test_openzeppelin_result_builder_rejects_backend_or_deployment_substitutes(self) -> None:
        cases = [
            (
                "wrong_generator",
                {
                    "tool_name": "openzeppelin-solidity-contracts-solidity-custom",
                    "verification_trace_refs": ["contextforge://control-plane/traces/openzeppelin-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "backend_health",
                {
                    "tool_name": "curl https://mcp.openzeppelin.com/contracts/solidity/mcp",
                    "verification_trace_refs": ["contextforge://control-plane/traces/openzeppelin-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "deployment_substitute",
                {
                    "tool_name": "openzeppelin-deploy-contract",
                    "verification_trace_refs": ["contextforge://control-plane/traces/openzeppelin-target-client"],
                },
                "no_matching_safe_tool",
            ),
            (
                "unsupported_safe_probe",
                {
                    "tool_name": "openzeppelin-solidity-contracts-solidity-erc20",
                    "safe_probe_id": "deploy-contract",
                    "verification_trace_refs": ["contextforge://control-plane/traces/openzeppelin-target-client"],
                },
                "unsupported_safe_probe_id",
            ),
            (
                "unsupported_proof",
                {
                    "tool_name": "openzeppelin-solidity-contracts-solidity-erc20",
                    "proof_kind": "backend_health",
                    "verification_trace_refs": ["contextforge://control-plane/traces/openzeppelin-target-client"],
                },
                "unsupported_proof_kind",
            ),
            (
                "missing_trace",
                {
                    "tool_name": "openzeppelin-solidity-contracts-solidity-erc20",
                    "verification_trace_refs": [],
                },
                "missing_target_client_trace",
            ),
            (
                "failed_probe",
                {
                    "tool_name": "openzeppelin-solidity-contracts-solidity-erc20",
                    "safe_probe_result": "error",
                    "status": "pending",
                    "verification_trace_refs": ["contextforge://control-plane/traces/openzeppelin-target-client"],
                },
                "safe_probe_not_passed",
            ),
        ]

        for name, kwargs, reason in cases:
            with self.subTest(name=name):
                result = common.build_safe_probe_validation_result(
                    "openzeppelin-solidity-contracts",
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
        self.assertIn('base.libraryName = "python"', text)
        self.assertIn('base.query = "standard library documentation lookup"', text)
        self.assertIn("for (const operation of service.safeOperations)", text)

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
