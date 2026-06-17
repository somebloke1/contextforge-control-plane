from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "validate_queue_dry_run.py"

spec = importlib.util.spec_from_file_location("validate_queue_dry_run", SCRIPT)
assert spec is not None
validate_queue_dry_run = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = validate_queue_dry_run
spec.loader.exec_module(validate_queue_dry_run)


class QueueDryRunValidationTests(unittest.TestCase):
    def test_normalize_codex_config_paths_rewrites_disposable_worktree_only(self) -> None:
        with tempfile.TemporaryDirectory(dir="/home/dgk/workspace") as tmp:
            worktree = Path(tmp)
            config = worktree / ".codex" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "\n".join(
                    [
                        '[mcp_servers.contextforge-helper]',
                        'command = "/home/dgk/workspace/cf-controlplane/.venv/bin/python"',
                        'args = ["/home/dgk/workspace/cf-controlplane/scripts/contextforge_helper_mcp.py"]',
                        'cwd = "/home/dgk/workspace/cf-controlplane"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            report = validate_queue_dry_run.normalize_codex_config_paths(worktree)

            text = config.read_text(encoding="utf-8")
            self.assertTrue(report["changed"])
            self.assertEqual(3, report["replacements"])
            self.assertIn(f'command = "{worktree}/.venv/bin/python"', text)
            self.assertIn(f'args = ["{worktree}/scripts/contextforge_helper_mcp.py"]', text)
            self.assertIn(f'cwd = "{worktree}"', text)
            self.assertNotIn("/home/dgk/workspace/cf-controlplane", text)

    def test_workspace_child_guard_accepts_only_workspace_children(self) -> None:
        with tempfile.TemporaryDirectory(dir="/home/dgk/workspace") as tmp:
            self.assertEqual(Path(tmp).resolve(), validate_queue_dry_run.ensure_workspace_child(Path(tmp)))

        with self.assertRaises(ValueError):
            validate_queue_dry_run.ensure_workspace_child(Path("/tmp/cf-controlplane-queue-dry-run"))

        with self.assertRaises(ValueError):
            validate_queue_dry_run.ensure_workspace_child(Path("/home/dgk/workspace"))

    def test_default_test_command_uses_canonical_venv_and_full_discovery(self) -> None:
        parser = validate_queue_dry_run.build_parser()
        args = parser.parse_args(["--head", "abc123"])
        test_command = args.test_command or [
            str(args.canonical_root / ".venv/bin/python"),
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ]

        self.assertEqual("/home/dgk/workspace/cf-controlplane/.venv/bin/python", test_command[0])
        self.assertEqual(["-m", "unittest", "discover", "-s", "tests", "-v"], test_command[1:])

    def test_script_defaults_preserve_canonical_config_contract(self) -> None:
        config = (REPO_ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
        precompact_test = (REPO_ROOT / "tests" / "test_codex_precompact_continuity_hook.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('/home/dgk/workspace/cf-controlplane/.venv/bin/python', config)
        self.assertIn('/home/dgk/workspace/cf-controlplane/scripts/contextforge_helper_mcp.py', config)
        self.assertIn('"/home/dgk/workspace/cf-controlplane"', precompact_test)
        self.assertIn("CONTEXTFORGE_CONFIG_CONTRACT_ROOT", precompact_test)
        self.assertIn(
            "replace_canonical_paths(before, canonical_root=canonical_root, worktree_root=worktree_root)",
            SCRIPT.read_text(encoding="utf-8"),
        )
        self.assertIn('test_env["CONTEXTFORGE_CONFIG_CONTRACT_ROOT"]', SCRIPT.read_text(encoding="utf-8"))

    def test_validation_docs_are_linked_from_activation_runbook(self) -> None:
        helper_doc = (REPO_ROOT / "docs" / "queue-dry-run-validation.md").read_text(encoding="utf-8")
        runbook = (REPO_ROOT / "docs" / "cf-controlplane-project-local-activation-runbook.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("scripts/validate_queue_dry_run.py", helper_doc)
        self.assertIn("docs/queue-dry-run-validation.md", runbook)
        self.assertIn("does not merge PRs", helper_doc)
        self.assertIn("disposable validation worktree", runbook)


if __name__ == "__main__":
    unittest.main()
