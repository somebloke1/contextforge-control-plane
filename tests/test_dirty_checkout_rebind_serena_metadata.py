from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import control_plane_project_state as project_state
import plan_dirty_checkout_rebind as dirty_rebind


class DirtyCheckoutSerenaMetadataTests(unittest.TestCase):
    def test_serena_project_metadata_legacy_name_requires_review(self) -> None:
        with tempfile.TemporaryDirectory(dir=project_state.WORKSPACE_ROOT) as tmp:
            base = Path(tmp).resolve()
            target = base / "cf-controlplane"
            legacy = base / "context-portal"
            target.mkdir()
            legacy.mkdir()
            serena_dir = target / ".serena"
            serena_dir.mkdir()
            metadata = serena_dir / "project.yml"
            metadata.write_text('project_name: "context-portal"\n', encoding="utf-8")

            report = dirty_rebind.build_report(
                target_root=target,
                legacy_root=legacy,
                approval_acknowledged=True,
                approval_ref="test-only",
                include_processes=False,
                client_types=("codex",),
            )

        surfaces = {surface["surface_id"]: surface for surface in report["surfaces"]}
        serena_metadata = surfaces["serena_project_metadata"]
        self.assertEqual("attention_required", serena_metadata["status"])
        self.assertFalse(serena_metadata["safe_to_leave_compatibility_slug"])
        self.assertIn("surface_contains_legacy_compatibility_slug", serena_metadata["warnings"])
        self.assertIn("serena_project_metadata:surface_contains_legacy_compatibility_slug", report["warnings"])

    def test_current_serena_project_metadata_uses_cf_controlplane_name(self) -> None:
        metadata = (REPO_ROOT / ".serena" / "project.yml").read_text(encoding="utf-8")

        self.assertIn('project_name: "cf-controlplane"', metadata)
        self.assertNotIn('project_name: "context-portal"', metadata)


if __name__ == "__main__":
    unittest.main()
