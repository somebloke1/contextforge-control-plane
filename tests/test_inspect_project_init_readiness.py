from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_state as project_state
import inspect_project_init_readiness as readiness


def write_fake_python(root: Path) -> None:
    python_path = root / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    python_path.chmod(0o755)


class ReadinessCompatibilityTests(unittest.TestCase):
    def test_serena_readiness_marks_legacy_slug_as_compatibility_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve() / "cf-controlplane"
            root.mkdir()
            write_fake_python(root)
            project_state.write_state_atomic(root, project_state.default_state(root, status="initialized"))
            legacy = root / "server-instances" / "serena-context-portal"
            legacy.mkdir(parents=True)
            (legacy / "instance.json").write_text(
                json.dumps(
                    {
                        "name": "serena-context-portal",
                        "canonical_project_root": str(root),
                        "server_name": "serena_context_portal_server",
                    }
                ),
                encoding="utf-8",
            )

            report = readiness.build_report(
                project_root=root,
                client_types=("codex",),
                include_processes=False,
            )

        serena = report["activation_artifacts"]["serena_project_instance"]
        self.assertEqual("attention_required", report["status"])
        self.assertIn("serena_project_instance_not_provisioned", report["warnings"])
        self.assertFalse(serena["expected"]["manifest_exists"])
        self.assertEqual("serena-cf-controlplane", serena["expected"]["instance_slug"].rsplit("-", 1)[0])
        self.assertTrue(serena["legacy"]["manifest_exists"])
        self.assertEqual(
            "canonical_instance_missing_compatibility_present",
            serena["readiness_decision"]["status"],
        )
        self.assertEqual(
            "compatibility_evidence_not_provisioning_completion",
            serena["readiness_decision"]["classification"],
        )
        self.assertTrue(serena["readiness_decision"]["hard_requirement"])
        self.assertIn("explicit approval", serena["readiness_decision"]["approval_boundary"])

    def test_compatibility_identifier_report_is_file_level_and_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            root = Path(tmp).resolve() / "cf-controlplane"
            root.mkdir()
            write_fake_python(root)
            project_state.write_state_atomic(root, project_state.default_state(root, status="initialized"))
            scripts = root / "scripts"
            scripts.mkdir()
            target = scripts / "project_init_common.py"
            target.write_text(
                'URI = "contextforge://context-portal/project-init/v15"\n'
                'SLUG = "serena-context-portal"\n',
                encoding="utf-8",
            )
            before = target.read_text(encoding="utf-8")

            report = readiness.build_report(
                project_root=root,
                client_types=("codex",),
                include_processes=False,
            )
            after = target.read_text(encoding="utf-8")

        self.assertEqual(before, after)
        compatibility = report["activation_artifacts"]["compatibility_identifiers"]
        self.assertEqual("#37", compatibility["policy"]["owner_issue"])
        self.assertFalse(compatibility["policy"]["broad_rename_allowed"])
        references = compatibility["references"]
        self.assertEqual(
            [
                {
                    "path": "scripts/project_init_common.py",
                    "identifier": "contextforge://context-portal/",
                    "count": 1,
                    "classification": "compatibility_pending_retirement",
                    "owner_issue": "#37",
                    "retirement_condition": (
                        "Retain only while compatibility naming is required, "
                        "or retire in a focused GitHub-tracked slice."
                    ),
                },
                {
                    "path": "scripts/project_init_common.py",
                    "identifier": "serena-context-portal",
                    "count": 1,
                    "classification": "compatibility_pending_retirement",
                    "owner_issue": "#37",
                    "retirement_condition": (
                        "Retain only while compatibility naming is required, "
                        "or retire in a focused GitHub-tracked slice."
                    ),
                },
            ],
            references,
        )


if __name__ == "__main__":
    unittest.main()
