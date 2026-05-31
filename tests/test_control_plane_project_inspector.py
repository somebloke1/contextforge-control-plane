from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_inspector as inspector_lib
import control_plane_project_state as state_lib


class ControlPlaneProjectInspectorTests(unittest.TestCase):
    def workspace_project(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(dir=state_lib.WORKSPACE_ROOT)

    def test_project_identity_is_root_bound_and_read_only(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            report = inspector_lib.ProjectInspector.for_root(root).project_identity()

        self.assertEqual(str(root), report["project"]["root"])
        self.assertTrue(report["safety"]["root_bound"])
        self.assertTrue(report["safety"]["read_only"])
        self.assertFalse(report["safety"]["shell_allowed"])
        self.assertFalse(report["safety"]["mutation_allowed"])
        self.assertFalse(report["safety"]["arbitrary_file_content_dump_allowed"])

    def test_detected_language_and_profile_hints_are_read_only(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")

            report = inspector_lib.ProjectInspector.for_root(root).detected_languages()

        matches = {item["language_id"]: item for item in report["matched_profiles"]}
        self.assertIn("python", matches)
        self.assertEqual("python", report["selected_primary_profile"]["language_id"])
        self.assertIn("does not install language tooling", report["non_actions"])

    def test_nested_roots_get_distinct_canonical_identity(self) -> None:
        with self.workspace_project() as tmp:
            outer = Path(tmp).resolve()
            inner = outer / "nested"
            inner.mkdir()

            outer_identity = inspector_lib.ProjectInspector.for_root(outer).project_identity()["project"]
            inner_identity = inspector_lib.ProjectInspector.for_root(inner).project_identity()["project"]

        self.assertNotEqual(outer_identity["root"], inner_identity["root"])
        self.assertNotEqual(outer_identity["root_hash"], inner_identity["root_hash"])
        self.assertTrue(inner_identity["root"].endswith("/nested"))

    def test_symlink_escape_is_blocked(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            outside = Path(tempfile.mkdtemp())
            try:
                (outside / "secret.txt").write_text("outside\n", encoding="utf-8")
                (root / "escape").symlink_to(outside)
                project = inspector_lib.ProjectInspector.for_root(root)
                with self.assertRaises(inspector_lib.ProjectInspectorAccessError):
                    project.classify_path("escape/secret.txt")
            finally:
                for child in outside.iterdir():
                    child.unlink()
                outside.rmdir()

    def test_ignored_paths_fail_closed(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            (root / "ignored.txt").write_text("ignored\n", encoding="utf-8")
            project = inspector_lib.ProjectInspector.for_root(root, evidence={"ignored_paths": ["ignored.txt"]})

            classification = project.classify_path("ignored.txt")
            with self.assertRaises(inspector_lib.ProjectInspectorAccessError):
                project.file_metadata("ignored.txt")
            summary = project.ignored_path_summary()

        self.assertEqual("denied_ignored", classification["status"])
        self.assertIn("ignored.txt", summary["ignored_paths"])
        self.assertEqual("caller_supplied_evidence_plus_static_defaults", summary["source"])

    def test_dirty_worktree_summary_uses_supplied_evidence_only(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            project = inspector_lib.ProjectInspector.for_root(
                root,
                evidence={
                    "dirty_worktree": {
                        "source": "fixture_status",
                        "clean": False,
                        "entries": [
                            {"path": "app.py", "status": "modified"},
                            {"path": "ignored.log", "status": "untracked"},
                        ],
                    },
                    "ignored_paths": ["ignored.log"],
                },
            )

            summary = project.dirty_worktree_summary()

        self.assertEqual("fixture_status", summary["source"])
        self.assertFalse(summary["clean"])
        self.assertEqual(1, summary["entry_count"])
        self.assertEqual("app.py", summary["entries"][0]["path"])
        self.assertFalse(summary["shell_executed"])

    def test_metadata_is_sanitized_and_does_not_dump_content_by_default(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            (root / "token.txt").write_text("Bearer <placeholder>\n", encoding="utf-8")
            project = inspector_lib.ProjectInspector.for_root(root)

            metadata = project.file_metadata("token.txt")

        self.assertEqual("<redacted>", metadata["relative_path"])
        self.assertEqual("file", metadata["kind"])
        self.assertEqual("computed", metadata["content_digest_status"])
        self.assertNotIn("snippet", metadata)
        self.assertNotIn("Bearer <placeholder>", str(metadata))

    def test_bounded_snippet_redacts_secret_like_content(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            (root / "notes.txt").write_text("hello\nBearer <placeholder>\n", encoding="utf-8")
            project = inspector_lib.ProjectInspector.for_root(root)

            metadata = project.file_metadata("notes.txt", include_snippet=True)

        self.assertEqual("bounded_sanitized_snippet", metadata["snippet"]["status"])
        self.assertNotIn("Bearer <placeholder>", str(metadata))
        self.assertGreaterEqual(metadata["snippet"]["redaction"]["redacted_value_count"], 1)

    def test_binary_and_large_content_requests_fail_closed(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            (root / "blob.bin").write_bytes(b"\x00\x01fixture")
            (root / "large.txt").write_text("x" * (inspector_lib.MAX_SNIPPET_BYTES + 1), encoding="utf-8")
            project = inspector_lib.ProjectInspector.for_root(root)

            with self.assertRaises(inspector_lib.ProjectInspectorRequestError):
                project.file_metadata("blob.bin", include_snippet=True)
            with self.assertRaises(inspector_lib.ProjectInspectorRequestError):
                project.file_metadata("large.txt", include_snippet=True)

    def test_shell_mutation_and_file_dump_requests_are_rejected(self) -> None:
        with self.workspace_project() as tmp:
            project = inspector_lib.ProjectInspector.for_root(Path(tmp).resolve())

            for tool_name in ("exec_command", "write_file", "read_file"):
                with self.subTest(tool_name=tool_name):
                    with self.assertRaises(inspector_lib.ProjectInspectorRequestError):
                        project.handle_request(tool_name, {"path": "x"})

    def test_module_does_not_call_shell_or_mutate_filesystem(self) -> None:
        with self.workspace_project() as tmp:
            root = Path(tmp).resolve()
            (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
            project = inspector_lib.ProjectInspector.for_root(root)
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

            with mock.patch.object(subprocess, "run", side_effect=AssertionError("shell called")):
                with mock.patch.object(os, "system", side_effect=AssertionError("shell called")):
                    report = project.inspect(paths=["pyproject.toml"])

            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

        self.assertEqual(before, after)
        self.assertIn("file_metadata", report)
        self.assertNotIn("shell called", str(report))


if __name__ == "__main__":
    unittest.main()
