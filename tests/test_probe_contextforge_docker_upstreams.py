from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import probe_contextforge_docker_upstreams as probe


def write_plan(root: Path) -> Path:
    path = root / "plan.json"
    path.write_text(
        json.dumps(
            {
                "services": [
                    {
                        "slug": "context7",
                        "target_upstream_url": "http://context7-transceiver:9203/mcp",
                        "locality": "compose_sidecar",
                        "approval_state": "available",
                        "approval_blocked": False,
                        "docker_projection_required": True,
                    },
                    {
                        "slug": "ssh-tmux",
                        "target_upstream_url": "http://host.docker.internal:9102/mcp",
                        "locality": "host_gateway_projection",
                        "approval_state": "blocked_pending_single_user_boundary_review",
                        "approval_blocked": True,
                        "docker_projection_required": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


class DockerUpstreamProbeTests(unittest.TestCase):
    def test_target_rows_can_filter_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = probe.read_plan(write_plan(Path(tmp)))

        rows = probe.target_rows(plan, {"ssh-tmux"})

        self.assertEqual(1, len(rows))
        self.assertEqual("ssh-tmux", rows[0]["slug"])
        self.assertTrue(rows[0]["approval_blocked"])

    def test_build_report_classifies_unreachable_host_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = write_plan(Path(tmp))
            targets = probe.target_rows(probe.read_plan(plan_path))
            report = probe.build_report(
                plan_path=plan_path,
                targets=targets,
                probe_rows=[
                    {**targets[0], "reachable": True, "status": 405, "reason": "Method Not Allowed"},
                    {**targets[1], "reachable": False, "error": "URLError", "message": "connection refused"},
                ],
                container="contextforge-harness-contextforge-gateway-1",
                timeout_seconds=5,
            )

        self.assertFalse(report["mutation_performed"])
        self.assertEqual(["context7"], report["summary"]["reachable_services"])
        self.assertEqual(["ssh-tmux"], report["summary"]["unreachable_services"])
        self.assertEqual(["ssh-tmux"], report["summary"]["host_gateway_unreachable_services"])
        self.assertEqual("http_reachable", report["services"][0]["reachability_class"])
        self.assertEqual("unreachable", report["services"][1]["reachability_class"])
        self.assertIn("no ContextForge API calls", report["non_actions"])


if __name__ == "__main__":
    unittest.main()
