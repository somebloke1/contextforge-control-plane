from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import inspect_stale_serena_test_units as inspector


LIST_UNITS = """\
UNIT                                                       LOAD   ACTIVE SUB     DESCRIPTION
contextforge-serena-cf-controlplane-d46fe58a2a20.service                 loaded active running ContextForge Serena backend
contextforge-serena-phronesis-devstack-cdb531b045e5.service loaded active running ContextForge Serena backend
contextforge-serena-test-new-proj-01-53f38d98c1fc.service  loaded active running ContextForge Serena backend
"""

LIST_UNIT_FILES = """\
UNIT FILE                                                  STATE   PRESET
contextforge-serena-cf-controlplane-d46fe58a2a20.service                 enabled enabled
contextforge-serena-phronesis-devstack-cdb531b045e5.service enabled enabled
contextforge-serena-test-new-proj-01-53f38d98c1fc.service  enabled enabled
"""

EXACT_TEST_UNITS = (
    ("contextforge-serena-test-new-proj-513815aaf602.service", "test-new-proj", 9110),
    ("contextforge-serena-test-new-proj-2-f110d0e0fc90.service", "test-new-proj-2", 9111),
    ("contextforge-serena-test-new-proj-3-02166c0c8608.service", "test-new-proj-3", 9112),
    ("contextforge-serena-test-new-proj-4-2fef6344632c.service", "test-new-proj-4", 9113),
    ("contextforge-serena-test-new-proj-5-9add9bd43f24.service", "test-new-proj-5", 9114),
    ("contextforge-serena-test-new-proj-01-53f38d98c1fc.service", "test-new-proj-01", 9115),
    ("contextforge-serena-test-new-proj-02-091f62efae24.service", "test-new-proj-02", 9116),
    ("contextforge-serena-test-new-proj-03-5de812b55b21.service", "test-new-proj-03", 9117),
)
RETIRED_PORTAL_SLUG = "-".join(("context", "portal"))
RETIRED_SERENA_UNIT = "contextforge-" + "-".join(("serena", RETIRED_PORTAL_SLUG)) + ".service"


class SerenaStaleUnitInspectorTests(unittest.TestCase):
    def test_report_classifies_compatibility_project_and_test_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cat_dir = root / "cat"
            cat_dir.mkdir()
            instance_dir = root / "server-instances" / "serena-test-new-proj-01-53f38d98c1fc"
            project_root = root / "test-new-proj-01"
            instance_dir.mkdir(parents=True)
            project_root.mkdir()
            (instance_dir / "instance.json").write_text(
                json.dumps({"canonical_project_root": str(project_root), "port": 9115}),
                encoding="utf-8",
            )
            cats = {
                "contextforge-serena-cf-controlplane-d46fe58a2a20.service": f"""
[Service]
ExecStart={root}/server-instances/serena-cf-controlplane-d46fe58a2a20/run-server.sh
""",
                "contextforge-serena-phronesis-devstack-cdb531b045e5.service": f"""
[Service]
ExecStart={root}/server-instances/serena-phronesis-devstack-cdb531b045e5/run-server.sh
""",
                "contextforge-serena-test-new-proj-01-53f38d98c1fc.service": f"""
[Service]
ExecStart={instance_dir}/run-server.sh --project {project_root}
""",
            }
            for unit, text in cats.items():
                (cat_dir / unit).write_text(text, encoding="utf-8")

            report = inspector.build_report(
                list_units_text=LIST_UNITS,
                list_unit_files_text=LIST_UNIT_FILES,
                unit_cat_dir=cat_dir,
            )

        by_unit = {unit["unit"]: unit for unit in report["units"]}
        self.assertEqual(
            "retain_compatibility_operator",
            by_unit["contextforge-serena-cf-controlplane-d46fe58a2a20.service"]["classification"],
        )
        self.assertEqual(
            "retain_project_scoped_or_unknown",
            by_unit["contextforge-serena-phronesis-devstack-cdb531b045e5.service"]["classification"],
        )
        test_unit = by_unit["contextforge-serena-test-new-proj-01-53f38d98c1fc.service"]
        self.assertEqual("disposable_candidate_requires_approval", test_unit["classification"])
        self.assertFalse(test_unit["cleanup_allowed"])
        self.assertTrue(test_unit["approval_required_for_cleanup"])
        self.assertEqual(str(project_root), test_unit["manifest_project_root"])
        self.assertEqual(str(project_root), test_unit["unit_project_root"])
        self.assertEqual({"exists": True, "type": "directory"}, test_unit["project_path_state"])
        self.assertEqual(9115, test_unit["port"])
        self.assertIn("read-only inspection; no systemd stop/disable/restart", report["non_actions"])
        self.assertIn(test_unit["unit"], report["summary"]["cleanup_candidate_units"])

    def test_test_unit_with_missing_manifest_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cat_dir = root / "cat"
            cat_dir.mkdir()
            project_root = root / "test-new-proj-01"
            project_root.mkdir()
            (cat_dir / "contextforge-serena-test-new-proj-01-53f38d98c1fc.service").write_text(
                "[Service]\n"
                f"ExecStart={root}/server-instances/serena-test-new-proj-01-53f38d98c1fc/run-server.sh "
                f"--project {project_root}\n",
                encoding="utf-8",
            )

            report = inspector.build_report(
                list_units_text=LIST_UNITS,
                list_unit_files_text=LIST_UNIT_FILES,
                unit_cat_dir=cat_dir,
            )

        by_unit = {unit["unit"]: unit for unit in report["units"]}
        unit = by_unit["contextforge-serena-test-new-proj-01-53f38d98c1fc.service"]
        self.assertEqual("review_required", unit["classification"])
        self.assertEqual([], report["summary"]["cleanup_candidate_units"])
        self.assertIn("manifest_present", unit["reasons"][0])

    def test_retired_runtime_surface_blocks_cleanup_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            retired_root = root / RETIRED_PORTAL_SLUG
            instance_dir = retired_root / "server-instances" / "-".join(("serena", RETIRED_PORTAL_SLUG))
            cat_dir = root / "cat"
            cat_dir.mkdir()
            instance_dir.mkdir(parents=True)
            retired_root.mkdir(exist_ok=True)
            (instance_dir / "instance.json").write_text(
                json.dumps({"canonical_project_root": str(retired_root), "port": 9108}),
                encoding="utf-8",
            )
            list_units = f"UNIT LOAD ACTIVE SUB DESCRIPTION\n{RETIRED_SERENA_UNIT} loaded active running ContextForge Serena backend\n"
            list_unit_files = f"UNIT FILE STATE PRESET\n{RETIRED_SERENA_UNIT} enabled enabled\n"
            (cat_dir / RETIRED_SERENA_UNIT).write_text(
                f"[Service]\nExecStart={instance_dir}/run-server.sh --project {retired_root}\n",
                encoding="utf-8",
            )

            report = inspector.build_report(
                list_units_text=list_units,
                list_unit_files_text=list_unit_files,
                unit_cat_dir=cat_dir,
            )

        self.assertEqual("attention_required", report["status"])
        by_unit = {unit["unit"]: unit for unit in report["units"]}
        unit = by_unit[RETIRED_SERENA_UNIT]
        self.assertEqual("retired_runtime_surface_requires_migration", unit["classification"])
        self.assertTrue(unit["blocks_cleanup_until_migrated"])
        self.assertFalse(unit["cleanup_allowed"])
        self.assertEqual([RETIRED_SERENA_UNIT], report["summary"]["retired_runtime_blocker_units"])
        self.assertEqual([], report["summary"]["cleanup_candidate_units"])

    def test_eight_exact_test_units_require_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cat_dir = root / "cat"
            cat_dir.mkdir()
            list_units = ["UNIT LOAD ACTIVE SUB DESCRIPTION"]
            list_unit_files = ["UNIT FILE STATE PRESET"]
            for unit, project_name, port in EXACT_TEST_UNITS:
                slug = unit.removesuffix(".service").removeprefix("contextforge-")
                instance_dir = root / "server-instances" / slug
                project_root = root / project_name
                instance_dir.mkdir(parents=True)
                project_root.mkdir()
                (instance_dir / "instance.json").write_text(
                    json.dumps({"canonical_project_root": str(project_root), "port": port}),
                    encoding="utf-8",
                )
                (cat_dir / unit).write_text(
                    f"[Service]\nExecStart={instance_dir}/run-server.sh --project {project_root}\n",
                    encoding="utf-8",
                )
                list_units.append(f"{unit} loaded active running ContextForge Serena backend")
                list_unit_files.append(f"{unit} enabled enabled")

            report = inspector.build_report(
                list_units_text="\n".join(list_units),
                list_unit_files_text="\n".join(list_unit_files),
                unit_cat_dir=cat_dir,
            )

        self.assertEqual(8, report["summary"]["classification_counts"]["disposable_candidate_requires_approval"])
        self.assertEqual(sorted(unit for unit, _project, _port in EXACT_TEST_UNITS), sorted(report["summary"]["cleanup_candidate_units"]))
        for unit in report["units"]:
            self.assertFalse(unit["cleanup_allowed"])
            self.assertTrue(unit["approval_required_for_cleanup"])

    def test_cli_uses_fixture_files_without_systemd_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            list_units = root / "list-units.txt"
            list_unit_files = root / "list-unit-files.txt"
            cat_dir = root / "cat"
            instance_dir = root / "server-instances" / "serena-test-new-proj-01-53f38d98c1fc"
            project_root = root / "test-new-proj-01"
            cat_dir.mkdir()
            instance_dir.mkdir(parents=True)
            project_root.mkdir()
            (instance_dir / "instance.json").write_text(
                json.dumps({"canonical_project_root": str(project_root), "port": 9115}),
                encoding="utf-8",
            )
            list_units.write_text(LIST_UNITS, encoding="utf-8")
            list_unit_files.write_text(LIST_UNIT_FILES, encoding="utf-8")
            (cat_dir / "contextforge-serena-test-new-proj-01-53f38d98c1fc.service").write_text(
                "[Service]\n"
                f"ExecStart={instance_dir}/run-server.sh --project {project_root}\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "inspect_stale_serena_test_units.py"),
                    "--list-units-file",
                    str(list_units),
                    "--list-unit-files-file",
                    str(list_unit_files),
                    "--unit-cat-dir",
                    str(cat_dir),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(inspector.SCHEMA_URI, report["schema_uri"])
        self.assertIn("ContextForge registry cleanup require separate explicit approval", report["approval_boundary"])

    def test_runbook_classifies_cf_controlplane_unit_as_compatibility(self) -> None:
        runbook = (REPO_ROOT / "docs" / "contextforge-wrapper-lifecycle-runbook.md").read_text(encoding="utf-8")

        self.assertIn("compatibility Serena", runbook)
        self.assertIn("not proof of canonical `cf-controlplane` Serena\nprovisioning", runbook)
        self.assertIn("Do not stop\n`contextforge-serena-cf-controlplane-d46fe58a2a20.service`", runbook)
        self.assertNotIn("is the canonical Serena\nbackend for this repository", runbook)


if __name__ == "__main__":
    unittest.main()
