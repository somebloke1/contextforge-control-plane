from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import manage_serena_project_instance as serena_manager
import project_init_common as common
import register_project_init_prompt as prompt_registration


class ProjectInitCommonTests(unittest.TestCase):
    def test_denied_roots_are_rejected(self) -> None:
        for root in ("/", str(Path.home()), "/home/dgk/workspace"):
            with self.subTest(root=root):
                with self.assertRaises(ValueError):
                    common.validate_project_root(root, require_workspace=True)

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

    def test_prompt_distinguishes_env_defaults_and_preflight_flow(self) -> None:
        text = prompt_registration.PROJECT_INIT_TEXT
        self.assertIn("otherwise hook defaults", text)
        self.assertIn("normal first-run hook default state", text)
        self.assertIn("status --project-root", text)
        self.assertIn("do not provision first", text)
        self.assertIn("related instances only", text)


if __name__ == "__main__":
    unittest.main()
