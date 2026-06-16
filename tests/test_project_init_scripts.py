from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import manage_serena_project_instance as serena_manager
import codex_project_init_hook as init_hook
import gemini_project_init_hook
import opencode_project_init_hook
import control_plane_contextforge_binding as binding
import control_plane_project_state as project_state
import project_init_common as common
import register_project_init_prompt as prompt_registration


CONSENT_REFS = ["run/consent-receipts/receipt-project-local-config.json"]


def service_descriptor(name: str = "context7") -> dict[str, object]:
    return {
        "service_family": name,
        "canonical_service": name,
        "service_binding": f"{name}:canonical",
        "codex_alias": common.normalize_codex_alias(name),
        "instantiation_class": "shared_canonical",
        "backend_instance": f"server-instances/{name}",
        "virtual_server": f"{common.normalize_codex_alias(name)}_server",
        "contextforge_readback_status": "matched",
        "gateway": f"{name}-gateway",
        "validation_policy": common.safe_validation_policy(name),
        "non_actions": ["do not create a per-project backend"],
    }


class ProjectInitCommonTests(unittest.TestCase):
    def test_denied_roots_are_rejected(self) -> None:
        for root in ("/", str(Path.home()), "/home/dgk/workspace"):
            with self.subTest(root=root):
                with self.assertRaises(ValueError):
                    common.validate_project_root(root, require_workspace=True)

    def test_cmu_math_foundations_root_is_safe(self) -> None:
        root = common.CMU_MATH_FOUNDATIONS_ROOT
        self.assertTrue(common.safe_workspace_project_root(root))
        self.assertEqual(root, common.validate_project_root(root, require_workspace=True))
        self.assertEqual(root / "dev", common.validate_project_root(root / "dev", require_workspace=True))

    def test_symlink_escape_is_not_a_safe_workspace_project(self) -> None:
        link = common.WORKSPACE_ROOT / "context-portal-test-symlink-escape"
        if link.exists() or link.is_symlink():
            link.unlink()
        try:
            link.symlink_to("/tmp")
            detected = common.detect_project_root(link)
            self.assertIsNone(detected)
            with self.assertRaises(ValueError):
                common.validate_project_root(link, require_workspace=True)
        finally:
            if link.exists() or link.is_symlink():
                link.unlink()

    def test_project_env_writes_only_whitelisted_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("EXISTING=value\nCONTEXTFORGE_SERENA_DECISION=unasked\n", encoding="utf-8")
            common.write_project_env(root, {common.ENV_SERENA_DECISION: "accepted"})
            self.assertEqual(
                "EXISTING=value\nCONTEXTFORGE_SERENA_DECISION=accepted\n",
                (root / ".env").read_text(encoding="utf-8"),
            )
            with self.assertRaises(ValueError):
                common.write_project_env(root, {"SECRET_TOKEN": "nope"})

    def test_identity_is_deterministic_for_uid_and_root(self) -> None:
        root = Path("/home/dgk/workspace/context-portal").resolve()
        self.assertEqual(common.project_root_hash(root, uid=1000), common.project_root_hash(root, uid=1000))
        self.assertNotEqual(common.project_root_hash(root, uid=1000), common.project_root_hash(root, uid=1001))

    def test_empty_nested_workspace_dir_is_its_own_project_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            parent = Path(tmp).resolve()
            (parent / ".env").write_text(
                "CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS=complete\n",
                encoding="utf-8",
            )
            child = parent / "empty-child"
            child.mkdir()
            self.assertEqual(child, common.detect_project_root(child))

    def test_non_empty_child_under_marker_root_still_uses_parent(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            parent = Path(tmp).resolve()
            (parent / ".env").write_text(
                "CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS=complete\n",
                encoding="utf-8",
            )
            child = parent / "non-empty-child"
            child.mkdir()
            (child / "notes.txt").write_text("not a separate empty project\n", encoding="utf-8")
            self.assertEqual(parent, common.detect_project_root(child))


class SerenaManagerTests(unittest.TestCase):
    def test_gemini_project_init_hook_uses_gemini_lifecycle_events(self) -> None:
        self.assertEqual({"SessionStart", "BeforeAgent"}, set(gemini_project_init_hook.GEMINI_HOOK_EVENTS))
        self.assertEqual({"experimental.chat.system.transform", "session.created"}, set(opencode_project_init_hook.OPENCODE_HOOK_EVENTS))
        self.assertEqual({"SessionStart", "UserPromptSubmit"}, set(init_hook.CODEX_HOOK_EVENTS))

    def test_gemini_project_init_hook_import_suppresses_gateway_stderr(self) -> None:
        cases = [
            ("gemini_project_init_hook", "GEMINI_HOOK_EVENTS", "BeforeAgent,SessionStart"),
            ("opencode_project_init_hook", "OPENCODE_HOOK_EVENTS", "experimental.chat.system.transform,session.created"),
        ]
        for module_name, attr_name, expected in cases:
            with self.subTest(module=module_name):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import sys; "
                            f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r}); "
                            f"import {module_name}; "
                            f"print(','.join(sorted({module_name}.{attr_name})))"
                        ),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("", result.stderr)
                self.assertEqual(expected, result.stdout.strip())

    def test_merge_codex_config_refuses_unmanaged_serena(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            config = root / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text("[mcp_servers.serena]\ncommand = \"serena\"\n", encoding="utf-8")
            identity = common.project_identity(root)
            with self.assertRaises(RuntimeError):
                serena_manager.merge_codex_config(identity)

    def test_merge_codex_config_manages_owned_block(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            identity = common.project_identity(root)
            serena_manager.merge_codex_config(identity)
            config = (root / ".codex/config.toml").read_text(encoding="utf-8")
            self.assertIn(f'contextforge-project-init-owner = "{identity.server_name}"', config)
            self.assertIn(str(serena_manager.WRAPPER_PATH), config)
            self.assertIn(identity.server_name, config)

    def test_create_respects_write_codex_config_flag(self) -> None:
        for write_codex_config in (False, True):
            with self.subTest(write_codex_config=write_codex_config):
                with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp, tempfile.TemporaryDirectory() as runtime:
                    root = Path(tmp).resolve()
                    runtime_root = Path(runtime)
                    repo_root = runtime_root / "repo"
                    repo_root.mkdir()
                    run_root = runtime_root / "run"
                    systemd_root = runtime_root / "systemd"
                    args = Namespace(
                        project_root=str(root),
                        require_workspace=True,
                        language=None,
                        replace_existing_serena_config=False,
                        verify=False,
                        app_server=False,
                        write_codex_config=write_codex_config,
                    )
                    with (
                        mock.patch.object(serena_manager, "REPO_ROOT", repo_root),
                        mock.patch.object(serena_manager, "RUN_ROOT", run_root),
                        mock.patch.object(serena_manager, "LOCK_PATH", run_root / "serena.lock"),
                        mock.patch.object(serena_manager, "SYSTEMD_USER_DIR", systemd_root),
                        mock.patch.object(serena_manager, "reserve_port", return_value=9119),
                        mock.patch.object(serena_manager, "verify_systemd_service"),
                        mock.patch.object(serena_manager, "wait_for_port"),
                        mock.patch.object(
                            serena_manager.gateway,
                            "_read_env",
                            return_value={
                                "PLATFORM_ADMIN_EMAIL": "admin@contextforge.dev",
                                "PLATFORM_ADMIN_PASSWORD": "password",
                            },
                        ),
                        mock.patch.object(serena_manager.gateway, "_token", return_value="token"),
                        mock.patch.object(
                            serena_manager,
                            "register_gateway_and_server",
                            return_value={"gateway_id": "gateway-1", "server_id": "server-1"},
                        ),
                        mock.patch.object(serena_manager, "merge_codex_config") as merge_codex_config,
                        contextlib.redirect_stdout(io.StringIO()),
                    ):
                        result = serena_manager.create(args)

                    self.assertEqual(0, result)
                    self.assertEqual(write_codex_config, merge_codex_config.called)

    def test_legacy_manifest_project_root_is_detected(self) -> None:
        data = {
            "scope": {"workspace_root": "/home/dgk/workspace/context-portal"},
            "backend": {"args": ["--project", "/wrong"]},
        }
        self.assertEqual(
            "/home/dgk/workspace/context-portal",
            serena_manager.manifest_project_root(data),
        )

    def test_app_server_status_shapes_are_parsed(self) -> None:
        server = {"name": "serena", "tools": {"a": {"name": "serena-project-get-current-config"}}}
        for response in (
            {"result": {"data": [server]}},
            {"result": {"servers": [server]}},
            {"result": [server]},
        ):
            self.assertEqual([server], serena_manager.app_server_servers(response))

    def test_app_server_tool_names_accept_dict_and_list(self) -> None:
        self.assertEqual(
            ["serena-project-get-current-config"],
            serena_manager.app_server_tool_names({"tools": {"x": {"name": "serena-project-get-current-config"}}}),
        )
        self.assertEqual(
            ["serena-project-get-current-config"],
            serena_manager.app_server_tool_names({"tools": [{"name": "serena-project-get-current-config"}]}),
        )

    def test_activate_exposure_uses_tool_names_not_config_text(self) -> None:
        server = {
            "name": "serena",
            "tools": {
                "config": {
                    "name": "serena-project-get-current-config",
                    "description": "Serena may report activate_project inside config text.",
                }
            },
        }
        names = serena_manager.app_server_tool_names(server)
        self.assertFalse(any("activate" in name for name in names))

    def test_empty_project_without_language_needs_choice(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / ".serena").mkdir()
            (root / ".serena/project.yml").write_text("languages: []\n", encoding="utf-8")
            state = serena_manager.language_state(root)
            self.assertEqual("needs_language", state["language_status"])
            self.assertTrue(state["needs_user_language_choice"])
            self.assertEqual(
                ["python", "typescript", "javascript", "rust", "go", "bash", "java", "csharp", "cpp"],
                state["recommended_language_examples"],
            )
            self.assertIn("--language LANGUAGE --verify --app-server", state["recommended_command"])
            self.assertEqual("ask_user_for_serena_language_before_create", state["next_action"])

    def test_status_require_workspace_rejects_denied_root(self) -> None:
        with self.assertRaises(ValueError):
            serena_manager.status(Namespace(project_root="/home/dgk", require_workspace=True, language=None))

    def test_empty_uninitialized_status_is_non_mutating_preflight(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = serena_manager.status(Namespace(project_root=str(root), require_workspace=True, language=None))
            after = sorted(path.relative_to(root) for path in root.rglob("*"))
            result = json.loads(stdout.getvalue())
            self.assertEqual(0, code)
            self.assertEqual(before, after)
            self.assertFalse(result["env_present"])
            self.assertTrue(result["needs_user_language_choice"])
            self.assertEqual("needs_language", result["language_status"])
            self.assertIn("--require-workspace", result["recommended_command"])

    def test_related_instances_reports_ancestor_without_selecting_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as workspace_tmp, tempfile.TemporaryDirectory() as repo_tmp:
            original_repo_root = serena_manager.REPO_ROOT
            try:
                serena_manager.REPO_ROOT = Path(repo_tmp)
                instances = serena_manager.REPO_ROOT / "server-instances/serena-parent"
                instances.mkdir(parents=True)
                parent = Path(workspace_tmp).resolve()
                child = parent / "child"
                child.mkdir()
                (instances / "instance.json").write_text(
                    json.dumps(
                        {
                            "canonical_project_root": str(parent),
                            "instance_slug": "serena-parent",
                            "server_name": "serena_parent_server",
                            "unit": "contextforge-serena-parent.service",
                            "port": 9119,
                        }
                    ),
                    encoding="utf-8",
                )
                related = serena_manager.related_serena_instances(child)
                self.assertEqual(1, len(related))
                self.assertEqual("ancestor", related[0]["relation"])
                self.assertEqual(str(parent), related[0]["project_root"])
                self.assertEqual("serena_parent_server", related[0]["server_name"])
            finally:
                serena_manager.REPO_ROOT = original_repo_root

    def test_language_inference_prefers_code_over_markdown(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / "README.md").write_text("# docs\n", encoding="utf-8")
            (root / "script.py").write_text("print('ok')\n", encoding="utf-8")
            self.assertEqual("python", serena_manager.infer_language(root))

    def test_language_override_writes_project_local_yml(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            changed = serena_manager.write_language_override(root, "python")
            self.assertTrue(changed)
            self.assertEqual(["python"], serena_manager.configured_languages(root))
            self.assertIn("languages:\n  - python\n", (root / ".serena/project.local.yml").read_text(encoding="utf-8"))

    def test_lsp_probe_uses_file_path_for_empty_project(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            path, created = serena_manager.find_probe_target(root, "python")
            self.assertTrue(created)
            self.assertIsNotNone(path)
            assert path is not None
            self.assertNotEqual(".", str(path.relative_to(root)))
            self.assertTrue(path.name.endswith(".py"))
            path.unlink()

    def test_optional_lsp_method_missing_is_advisory(self) -> None:
        classified = serena_manager.classify_lsp_probe_response(
            "find_implementations",
            {"error": {"code": -32601, "message": "method not found"}},
            baseline=False,
        )
        self.assertTrue(classified["ok"])
        self.assertEqual("unsupported_by_lsp_backend", classified["classification"])
        self.assertEqual("optional_capability_gap", classified["severity"])

    def test_baseline_lsp_method_missing_is_blocking(self) -> None:
        classified = serena_manager.classify_lsp_probe_response(
            "get_symbols_overview",
            {"error": {"code": -32601, "message": "method not found"}},
            baseline=True,
        )
        self.assertFalse(classified["ok"])
        self.assertEqual("baseline_blocking", classified["severity"])

    def test_baseline_lsp_tool_error_text_is_blocking(self) -> None:
        classified = serena_manager.classify_lsp_probe_response(
            "get_symbols_overview",
            {"result": {"content": [{"text": "Error executing tool: Exception - language server manager is not initialized"}]}},
            baseline=True,
        )
        self.assertFalse(classified["ok"])
        self.assertEqual("probe_error", classified["classification"])
        self.assertEqual("baseline_blocking", classified["severity"])

    def test_automatic_lsp_probes_are_read_only(self) -> None:
        suffixes = serena_manager.automatic_lsp_probe_tool_suffixes(include_optional=True)
        self.assertIn("find-implementations", suffixes)
        self.assertFalse(set(suffixes) & set(serena_manager.EDIT_LSP_TOOL_SUFFIXES))

    def test_python_find_implementations_gap_is_optional(self) -> None:
        gap = serena_manager.unsupported_optional_gap("find_implementations", "find-implementations")
        self.assertEqual("optional_capability_gap", gap["severity"])
        self.assertEqual("unsupported_by_lsp_backend", gap["classification"])

    def test_javascript_backend_options_normalize_to_typescript(self) -> None:
        self.assertEqual("typescript", serena_manager.validate_language("javascript"))
        options = serena_manager.lsp_backend_options("javascript")
        self.assertLessEqual(len(options), 3)
        self.assertEqual("typescript", options[0]["backend_id"])
        self.assertEqual("javascript", options[0]["requested_language"])
        self.assertEqual("typescript", options[0]["normalized_language"])

    def test_backend_catalog_returns_user_facing_choices(self) -> None:
        options = serena_manager.lsp_backend_options("python")
        self.assertLessEqual(len(options), 3)
        self.assertTrue(all(option["label"] for option in options))
        self.assertTrue(all(option["recommended_scope"] == "instance" for option in options))
        self.assertFalse(any(option["install_implemented"] for option in options))

    def test_status_output_includes_lsp_advisory_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / "script.py").write_text("print('ok')\n", encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = serena_manager.status(Namespace(project_root=str(root), require_workspace=True, language=None))
            result = json.loads(stdout.getvalue())
            self.assertEqual(0, code)
            for key in (
                "lsp_capability_status",
                "lsp_gap_severity",
                "optional_capability_gaps",
                "lsp_backend_options",
                "lsp_next_action",
                "lsp_instance_scope",
            ):
                self.assertIn(key, result)

    def test_verify_without_manifest_includes_lsp_advisory_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            (root / "script.py").write_text("print('ok')\n", encoding="utf-8")
            result = serena_manager.build_verify_result(
                Namespace(project_root=str(root), require_workspace=True, language=None, app_server=False)
            )
            self.assertFalse(result["ok"])
            self.assertIn("lsp_capability_status", result)
            self.assertIn("lsp_backend_options", result)

    def test_instance_lsp_scaffold_is_local_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instance = Path(tmp) / "serena-test"
            scaffold = serena_manager.ensure_lsp_scaffold(instance, "python")
            self.assertTrue((instance / "lsp-tools/bin").is_dir())
            self.assertTrue((instance / "lsp-tools/cache").is_dir())
            self.assertTrue((instance / "lsp-tools/logs").is_dir())
            self.assertTrue((instance / "lsp-tools/solidlsp").is_dir())
            self.assertTrue((instance / "lsp.env").is_file())
            self.assertEqual(str(instance / "lsp-tools"), scaffold["lsp_tools_dir"])
            manifest = json.loads((instance / "lsp-tools/manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["install_command_execution_enabled"])

    def test_lsp_scaffold_rejects_symlink_and_world_writable_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symlink_instance = root / "symlink-instance"
            symlink_instance.symlink_to("/tmp")
            with self.assertRaises(RuntimeError):
                serena_manager.ensure_lsp_scaffold(symlink_instance, "python")

            instance = root / "world-writable-instance"
            (instance / "lsp-tools").mkdir(parents=True)
            (instance / "lsp-tools").chmod(0o777)
            try:
                with self.assertRaises(RuntimeError):
                    serena_manager.ensure_lsp_scaffold(instance, "python")
            finally:
                (instance / "lsp-tools").chmod(0o755)

    def test_manifest_merge_preserves_existing_fields_while_adding_lsp(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.WORKSPACE_ROOT) as tmp:
            project = Path(tmp).resolve()
            identity = common.project_identity(project)
            with tempfile.TemporaryDirectory() as instance_tmp:
                instance = Path(instance_tmp)
                (instance / "instance.json").write_text(
                    json.dumps(
                        {
                            "contextforge": {"gateway": {"id": "existing"}},
                            "runtime": {"kept": True},
                            "custom_future_field": "preserve-me",
                        }
                    ),
                    encoding="utf-8",
                )
                serena_manager.write_manifest(
                    instance,
                    identity,
                    9111,
                    lsp_metadata={"advisory_status": "instance_scaffold_ready"},
                )
                manifest = json.loads((instance / "instance.json").read_text(encoding="utf-8"))
                self.assertEqual({"gateway": {"id": "existing"}}, manifest["contextforge"])
                self.assertEqual({"kept": True}, manifest["runtime"])
                self.assertEqual("preserve-me", manifest["custom_future_field"])
                self.assertEqual("instance_scaffold_ready", manifest["lsp"]["advisory_status"])

    def test_install_commands_are_not_enabled(self) -> None:
        self.assertFalse(serena_manager.install_command_execution_enabled())
        self.assertFalse(any(option["install_implemented"] for option in serena_manager.lsp_backend_options("rust")))

    def test_prompt_distinguishes_env_defaults_and_preflight_flow(self) -> None:
        text = prompt_registration.PROJECT_INIT_TEXT
        self.assertIn(".project/context_forge_state.json is the project initialization authority", text)
        self.assertIn("Do not echo this context to the user", text)
        self.assertIn("hidden or structured prompt/context injection", text)
        self.assertIn("User-visible UI should be limited to information that requires user understanding or response", text)
        self.assertIn("Ask exactly one question, then stop and wait", text)
        self.assertIn("Which ContextForge services should I activate for this project?", text)
        self.assertIn("No user-global config/trust/extension changes", text)
        self.assertIn("for Pi this is .project/context_forge_state.json records", text)
        self.assertIn("for OpenCode this is project-local opencode.json plus .opencode/plugins/contextforge-project-init.js", text)
        self.assertIn("before_agent_start system-prompt context", text)
        self.assertIn("experimental.chat.system.transform system context", text)
        self.assertIn("cf_project_init_prompt and cf_contextforge_pi_readback are diagnostic only", text)
        self.assertIn("do not reconstruct the full plan object from visible text", text)
        self.assertIn("prefer those cached id/digest tools over reconstructing a full plan object", text)
        self.assertIn("call cf_project_init_apply using the cached plan and receipts", text)
        self.assertIn("status=config_conflict with an embedded recovery_plan", text)
        self.assertIn("call cf_project_init_recovery_approve with the exact recovery challenge id and recovery plan digest", text)
        self.assertIn("call cf_project_init_recovery_apply using the cached recovery plan and receipts", text)
        self.assertIn("Do not call apply_project_init_recovery with only plan_id, plan_digest, or receipt ids", text)
        self.assertIn("complete helper-returned recovery plan object and full receipt objects", text)
        self.assertIn("keep them together in the helper recovery approval/apply path", text)
        self.assertIn("Never choose service selections, approval, reload acknowledgement, validation", text)
        self.assertIn("If the user echoes your question, asks you to provide the selection numbers", text)
        self.assertIn("Do not invoke project-init helper scripts or Python modules through shell", text)
        self.assertIn("helper cache is missing or stale", text)
        self.assertIn("do not silently replace the challenge id", text)
        self.assertIn("first call cf_project_init_record_client_reload", text)
        self.assertIn("honor that choice after recording the reload acknowledgement instead of asking again", text)
        self.assertIn("after the reload or new session, resume project init", text)
        self.assertIn("Codex launches configured MCP servers and exposes their tools when a session starts", text)
        self.assertIn("/mcp is a status view, not an in-place MCP tool reload", text)
        self.assertIn("start a new Codex session from the project root before target-client-visible validation", text)
        self.assertIn("start a new OpenCode session from the project root before target-client-visible validation", text)
        self.assertIn("the Pi agent must issue /reload before validation", text)
        self.assertIn("Choose 1 to validate now", text)
        self.assertIn("Do not call unlisted or unavailable validation tool names", text)
        self.assertIn("validation tool call is missing, not found, unavailable, or returns an error", text)
        self.assertIn("Skipped-service follow-up", text)
        self.assertIn("Do not substitute built-in web search, direct shell commands, direct SSH/tmux", text)
        self.assertIn("service remains skipped/not verified", text)
        self.assertIn("numbered option list", text)
        self.assertIn("status --project-root", text)
        self.assertIn("Serena is one project-scoped option in this menu, not the whole flow", text)
        self.assertIn("target-client-visible and non-destructive", text)

    def test_prompt_registration_help_and_dry_run_do_not_call_gateway(self) -> None:
        original_read_env = prompt_registration.gateway._read_env
        try:
            def fail_read_env(_path: object) -> dict[str, str]:
                raise AssertionError("gateway env should not be read for help or dry-run")

            prompt_registration.gateway._read_env = fail_read_env  # type: ignore[assignment]
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as help_exit:
                    prompt_registration.main(["--help"])
            self.assertEqual(0, help_exit.exception.code)

            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(0, prompt_registration.main(["--dry-run"]))
            self.assertIn("would_register project_init_prompt", stdout.getvalue())
        finally:
            prompt_registration.gateway._read_env = original_read_env  # type: ignore[assignment]

    def test_project_init_artifact_uris_track_semantic_prompt_version(self) -> None:
        self.assertTrue(common.PROJECT_INIT_RESOURCE_URI.endswith(f"/{common.PROMPT_VERSION}"))
        self.assertTrue(common.SERENA_GUIDANCE_RESOURCE_URI.endswith(f"/{common.PROMPT_VERSION}"))
        self.assertIn(common.PROMPT_VERSION, common.PROJECT_INIT_RESOURCE_NAME)
        self.assertIn(common.PROMPT_VERSION, common.SERENA_GUIDANCE_RESOURCE_NAME)
        self.assertNotRegex(common.PROJECT_INIT_RESOURCE_URI, r"/v1(?:/|$)")

    def test_hook_rejects_stale_registered_serena_only_prompt(self) -> None:
        stale = (
            "ContextForge project initialization, version v1. "
            "Ask the user whether to enable a project-local Serena backend. "
            "First-run initialization asks only for Serena enablement."
        )
        self.assertFalse(init_hook.prompt_text_is_fresh(stale))

        identity = common.project_identity("/home/dgk/workspace/test-new-proj-03")
        rendered = init_hook.render_local_prompt(init_hook.prompt_args(identity, {}))

        self.assertTrue(init_hook.prompt_text_is_fresh(rendered))
        self.assertIn("Ask exactly one question, then stop and wait", rendered)
        self.assertIn("/home/dgk/workspace/test-new-proj-03", rendered)
        self.assertIn(f"ContextForge project initialization, version {common.PROMPT_VERSION}", rendered)

    def test_hook_decision_uses_project_init_lifecycle_inspector(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            self.assertTrue(init_hook.should_inject(root, {}))

            initialized = project_state.default_state(root, status="initialized")
            project_state.write_state_atomic(root, initialized)
            self.assertFalse(init_hook.should_inject(root, {}))

            disabled = project_state.load_state(root)
            assert disabled is not None
            disabled["status"] = "disabled"
            project_state.write_state_atomic(root, disabled)
            self.assertFalse(init_hook.should_inject(root, {}))

            pending = project_state.load_state(root)
            assert pending is not None
            pending["status"] = "in_progress"
            pending["project_init"]["x_hook_prompt_state"] = "active"
            project_state.write_state_atomic(root, pending)
            self.assertTrue(init_hook.should_inject(root, {}))

            completed_unverified = project_state.load_state(root)
            assert completed_unverified is not None
            completed_unverified["project_init"]["x_hook_prompt_state"] = "completed_unverified"
            project_state.write_state_atomic(root, completed_unverified)
            self.assertFalse(init_hook.should_inject(root, {}))

    def test_hook_suppression_is_target_client_aware(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="")
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="validate_now")
            state = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": True}},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, state)

            self.assertFalse(init_hook.should_inject(root, {}, target_client="codex"))
            self.assertTrue(init_hook.should_inject(root, {}, target_client="gemini"))
            self.assertTrue(init_hook.should_inject(root, {}, target_client="opencode"))

            gemini_plan = binding.plan_project_init_gemini_config_write(root, [service])
            gemini_state = project_state.apply_project_init_activation_to_state(
                state,
                [service],
                target_client="gemini",
                client_config_plan=gemini_plan,
                validation_plan=binding.build_project_init_validation_plan([service], validation_mode="validate_now", target_client="gemini"),
                validation_results={"context7:canonical": {"status": "passed", "target_client_visible": True}},
                consent_receipt_refs=CONSENT_REFS,
            )
            project_state.write_state_atomic(root, gemini_state)
            self.assertFalse(init_hook.should_inject(root, {}, target_client="gemini"))
            self.assertTrue(init_hook.should_inject(root, {}, target_client="opencode"))

    def test_hook_decision_repairs_invalid_current_shape_without_fresh_init_classification(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve()
            service = service_descriptor("context7")
            config_plan = binding.plan_project_init_codex_config_write(root, [service], existing_text="[mcp_servers.context7]\ncommand = \"npx\"\n")
            validation_plan = binding.build_project_init_validation_plan([service], validation_mode="pending_choice")
            raw = project_state.apply_project_init_activation_to_state(
                project_state.default_state(root),
                [service],
                target_client="codex",
                client_config_plan=config_plan,
                validation_plan=validation_plan,
                validation_results={},
                consent_receipt_refs=CONSENT_REFS,
            )
            raw.pop("project_init")
            project_state.project_state_path(root).parent.mkdir(parents=True)
            project_state.project_state_path(root).write_text(json.dumps(raw), encoding="utf-8")

            inspection = init_hook.project_state_inspection(root)
            args = init_hook.prompt_args(common.project_identity(root), {})
            should_inject = init_hook.should_inject(root, {})

        self.assertTrue(should_inject)
        self.assertEqual("invalid_repairable", inspection["lifecycle_status"])
        self.assertEqual("repair_project_init_state", inspection["recommended_action"])
        self.assertEqual("invalid_repairable", args["project_state_lifecycle_status"])
        self.assertEqual("repair_project_init_state", args["project_state_recommended_action"])

    def test_hook_prompt_metadata_requires_current_semantic_version_tag(self) -> None:
        self.assertTrue(
            init_hook.prompt_record_is_fresh(
                {
                    "id": "prompt-v6",
                    "name": common.PROJECT_INIT_PROMPT_NAME,
                    "tags": ["contextforge", "project-init", common.PROMPT_VERSION],
                }
            )
        )
        self.assertTrue(
            init_hook.prompt_record_is_fresh(
                {
                    "id": "prompt-v6",
                    "name": common.PROJECT_INIT_PROMPT_NAME,
                    "tags": [{"name": common.PROMPT_VERSION}],
                }
            )
        )
        self.assertFalse(
            init_hook.prompt_record_is_fresh(
                {
                    "id": "prompt-v1",
                    "name": common.PROJECT_INIT_PROMPT_NAME,
                    "tags": ["contextforge", "project-init", "v1"],
                }
            )
        )
        self.assertFalse(init_hook.prompt_record_is_fresh({"name": common.PROJECT_INIT_PROMPT_NAME, "tags": [common.PROMPT_VERSION]}))

    def test_hook_resource_metadata_requires_current_semantic_version_uri_and_tag(self) -> None:
        self.assertTrue(
            init_hook.resource_record_is_fresh(
                {
                    "id": "resource-v6",
                    "uri": common.PROJECT_INIT_RESOURCE_URI,
                    "tags": ["contextforge", "project-init", common.PROMPT_VERSION],
                }
            )
        )
        self.assertFalse(
            init_hook.resource_record_is_fresh(
                {
                    "id": "resource-v1",
                    "uri": "contextforge://context-portal/project-init/v1",
                    "tags": ["contextforge", "project-init", common.PROMPT_VERSION],
                }
            )
        )
        self.assertFalse(
            init_hook.resource_record_is_fresh(
                {
                    "id": "resource-v6",
                    "uri": common.PROJECT_INIT_RESOURCE_URI,
                    "tags": ["contextforge", "project-init", "v1"],
                }
            )
        )

    def test_hook_self_upgrade_upserts_project_init_prompt_and_resource(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []
        original_resource = prompt_registration.upsert_resource
        original_prompt = prompt_registration.upsert_prompt
        try:
            def fake_resource(token: str, **kwargs: object) -> dict[str, object]:
                calls.append(("resource", kwargs))
                self.assertEqual("token", token)
                return {"id": "resource-v6"}

            def fake_prompt(token: str, **kwargs: object) -> dict[str, object]:
                calls.append(("prompt", kwargs))
                self.assertEqual("token", token)
                return {"id": "prompt-v6"}

            prompt_registration.upsert_resource = fake_resource  # type: ignore[assignment]
            prompt_registration.upsert_prompt = fake_prompt  # type: ignore[assignment]

            prompt_id = init_hook.upgrade_project_init_prompt("token")
        finally:
            prompt_registration.upsert_resource = original_resource  # type: ignore[assignment]
            prompt_registration.upsert_prompt = original_prompt  # type: ignore[assignment]

        self.assertEqual("prompt-v6", prompt_id)
        self.assertEqual(["resource", "prompt"], [name for name, _kwargs in calls])
        self.assertEqual(common.PROJECT_INIT_RESOURCE_NAME, calls[0][1]["name"])
        self.assertEqual(common.PROJECT_INIT_RESOURCE_URI, calls[0][1]["uri"])
        self.assertEqual(common.PROJECT_INIT_PROMPT_NAME, calls[1][1]["name"])
        self.assertIn(common.PROMPT_VERSION, calls[0][1]["tags"])
        self.assertIn(common.PROMPT_VERSION, calls[1][1]["tags"])
        self.assertIn("version {{ prompt_version }}", str(calls[1][1]["template"]))

    def test_hook_renders_upgraded_prompt_when_registered_prompt_is_stale(self) -> None:
        identity = common.project_identity("/home/dgk/workspace/test-new-proj-03")
        original_request = init_hook.gateway._request
        original_upgrade = init_hook.upgrade_project_init_prompt
        upgrade_calls: list[str] = []
        try:
            def fake_request(method: str, path: str, *, token: str, body: dict[str, str] | None = None) -> dict[str, object]:
                self.assertEqual("POST", method)
                if path == "/prompts/stale":
                    return {"messages": [{"content": {"text": "ContextForge project initialization, version v1. Serena only."}}]}
                if path == "/prompts/upgraded":
                    return {"messages": [{"content": {"text": init_hook.render_local_prompt(body or {})}}]}
                raise AssertionError(f"unexpected path: {path}")

            def fake_upgrade(token: str) -> str:
                upgrade_calls.append(token)
                return "upgraded"

            init_hook.gateway._request = fake_request  # type: ignore[assignment]
            init_hook.upgrade_project_init_prompt = fake_upgrade  # type: ignore[assignment]

            rendered = init_hook.render_prompt("token", "stale", identity, {})
        finally:
            init_hook.gateway._request = original_request  # type: ignore[assignment]
            init_hook.upgrade_project_init_prompt = original_upgrade  # type: ignore[assignment]

        self.assertEqual(["token"], upgrade_calls)
        self.assertTrue(init_hook.prompt_text_is_fresh(rendered))
        self.assertIn(f"ContextForge project initialization, version {common.PROMPT_VERSION}", rendered)


if __name__ == "__main__":
    unittest.main()
