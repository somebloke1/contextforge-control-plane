from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import install_user_systemd


class InstallUserSystemdPlanTests(unittest.TestCase):
    def test_plan_reports_no_mutation_and_desired_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = install_user_systemd.build_install_plan(user_unit_dir=Path(tmp))

        self.assertEqual(install_user_systemd.PLAN_SCHEMA_URI, plan["schema_uri"])
        self.assertFalse(plan["mutation_performed"])
        self.assertIn("read-only plan; no systemctl command executed", plan["non_actions"])
        self.assertEqual(len(install_user_systemd.units()), plan["summary"]["desired_unit_count"])
        self.assertEqual(0, plan["summary"]["installed_unit_count"])
        self.assertEqual(plan["summary"]["desired_unit_count"], plan["summary"]["write_or_replace_count"])
        by_unit = {unit["unit"]: unit for unit in plan["units"]}
        self.assertIn("contextforge-time.service", by_unit)
        desired_time = install_user_systemd.units()["contextforge-time.service"]
        self.assertIn("server-instances/time/run-bridge.sh", desired_time)
        self.assertIn("EnvironmentFile=-", desired_time)
        self.assertIn("server-instances/time/.env", desired_time)
        self.assertEqual(
            [
                {
                    "path": str(REPO_ROOT / "server-instances" / "time" / ".env"),
                    "optional": True,
                    "exists": False,
                    "is_file": False,
                }
            ],
            by_unit["contextforge-time.service"]["desired_environment_files"],
        )

    def test_plan_detects_external_workspace_root_in_current_unit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            (unit_dir / "contextforge-gateway.service").write_text(
                "[Service]\n"
                "WorkingDirectory=/home/dgk/workspace/example-legacy-root\n"
                "EnvironmentFile=/home/dgk/workspace/example-legacy-root/config/contextforge.env\n"
                "ExecStart=/home/dgk/workspace/example-legacy-root/.venv/bin/mcpgateway\n",
                encoding="utf-8",
            )

            plan = install_user_systemd.build_install_plan(user_unit_dir=unit_dir)

        by_unit = {unit["unit"]: unit for unit in plan["units"]}
        gateway = by_unit["contextforge-gateway.service"]
        self.assertTrue(gateway["installed"])
        self.assertFalse(gateway["current_matches_desired"])
        self.assertEqual(
            ["/home/dgk/workspace/example-legacy-root"],
            gateway["current_workspace_roots_outside_repo"],
        )
        self.assertEqual(
            ["/home/dgk/workspace/example-legacy-root"],
            [unit for unit in gateway["current_workspace_roots_outside_repo"]],
        )

    def test_plan_records_env_file_existence_without_reading_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unit_dir = Path(tmp)
            env_file = unit_dir / "service.env"
            env_file.write_text("SECRET_VALUE=not-read-by-plan\n", encoding="utf-8")
            (unit_dir / "contextforge-context7.service").write_text(
                "[Service]\n"
                f"EnvironmentFile=-{env_file}\n"
                "ExecStart=/bin/true\n",
                encoding="utf-8",
            )

            plan = install_user_systemd.build_install_plan(user_unit_dir=unit_dir)

        by_unit = {unit["unit"]: unit for unit in plan["units"]}
        refs = by_unit["contextforge-context7.service"]["current_environment_files"]
        self.assertEqual([{"path": str(env_file), "optional": True, "exists": True, "is_file": True}], refs)
        self.assertNotIn("not-read-by-plan", json.dumps(plan))

    def test_plan_json_cli_does_not_run_systemctl(self) -> None:
        with mock.patch.object(install_user_systemd, "run_systemctl") as run_systemctl:
            with mock.patch.object(sys, "argv", ["install_user_systemd.py", "--plan-json"]):
                with mock.patch("builtins.print") as print_mock:
                    self.assertEqual(0, install_user_systemd.main())

        run_systemctl.assert_not_called()
        output = print_mock.call_args.args[0]
        data = json.loads(output)
        self.assertFalse(data["mutation_performed"])

    def test_cli_plan_subprocess_smoke(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "install_user_systemd.py"),
                "--plan-json",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["mutation_performed"])


if __name__ == "__main__":
    unittest.main()
