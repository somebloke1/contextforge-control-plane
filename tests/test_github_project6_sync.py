from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "github_project6_sync.py"

spec = importlib.util.spec_from_file_location("github_project6_sync", SCRIPT)
assert spec is not None
github_project6_sync = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = github_project6_sync
spec.loader.exec_module(github_project6_sync)


def command_result(args: list[str], payload: object) -> object:
    return github_project6_sync.CommandResult(args, 0, json.dumps(payload), "")


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> object:
        self.calls.append(args)
        command = " ".join(args)
        if args[:3] == ["gh", "project", "view"]:
            return command_result(args, {"id": "PVT_project", "number": 6, "title": "cf-controlplane-project"})
        if args[:3] == ["gh", "project", "field-list"]:
            return command_result(
                args,
                {
                    "fields": [
                        {
                            "id": "field_agent",
                            "name": "Agent state",
                            "type": "ProjectV2SingleSelectField",
                            "options": [
                                {"id": "opt_ready", "name": "Ready"},
                                {"id": "opt_active", "name": "Active"},
                            ],
                        },
                        {
                            "id": "field_deps",
                            "name": "Dependency clues",
                            "type": "ProjectV2Field",
                        },
                    ],
                    "totalCount": 2,
                },
            )
        if args[:3] == ["gh", "project", "item-list"]:
            return command_result(
                args,
                {
                    "items": [
                        {
                            "id": "item_166",
                            "title": "Add low-quota GitHub Project 6 sync helper",
                            "agent state": "Ready",
                            "content": {
                                "number": 166,
                                "title": "Add low-quota GitHub Project 6 sync helper",
                                "type": "Issue",
                            },
                        }
                    ],
                    "totalCount": 1,
                },
            )
        if args[:3] == ["gh", "api", "repos/example-owner/example-repo/issues?state=open&per_page=100"]:
            return command_result(
                args,
                [
                    {
                        "number": 166,
                        "title": "Add low-quota GitHub Project 6 sync helper",
                        "state": "open",
                        "html_url": "https://github.com/example-owner/example-repo/issues/166",
                        "labels": [{"name": "enhancement"}],
                        "updated_at": "2026-06-18T09:00:00Z",
                    }
                ],
            )
        if args[:3] == ["gh", "api", "rate_limit"]:
            return command_result(
                args,
                {
                    "core": {"limit": 5000, "remaining": 4999},
                    "graphql": {"limit": 5000, "remaining": 4500},
                },
            )
        if args[:3] == ["gh", "api", "graphql"]:
            if "rateLimit" in args[-1]:
                return command_result(
                    args,
                    {"data": {"rateLimit": {"cost": 1, "remaining": 4499, "resetAt": "2026-06-18T10:00:00Z"}}},
                )
            return command_result(args, {"data": {"u0": {"projectV2Item": {"id": "item_166"}}}})
        raise AssertionError(f"unexpected command: {command}")


class GitHubProject6SyncTests(unittest.TestCase):
    def test_snapshot_caches_schema_and_separates_rest_issue_reads(self) -> None:
        runner = FakeRunner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = github_project6_sync.ensure_generated_local_json(
                Path("generated/project6-cache.local.json"),
                repo_root=root,
            )

            snapshot = github_project6_sync.build_snapshot(
                owner="example-owner",
                project_number=6,
                repo="example-owner/example-repo",
                query="-status:Done",
                limit=80,
                ttl_seconds=900,
                cache_path=cache,
                refresh_cache=False,
                now=1234,
                runner=runner,
            )

            self.assertTrue(cache.exists())
            self.assertEqual("PVT_project", snapshot["project"]["id"])
            self.assertEqual("field_agent", snapshot["fields"]["Agent state"]["id"])
            self.assertEqual("item_166", snapshot["item_ids_by_key"]["#166"])
            self.assertEqual("Issue", snapshot["rest_issue_pr_summary"][0]["type"])
            self.assertEqual(1, snapshot["rate_limit"]["graphql_query"]["cost"])
            self.assertIn("rest_issue_pr_substance", snapshot["commands"])
            self.assertIn(["gh", "api", "repos/example-owner/example-repo/issues?state=open&per_page=100"], runner.calls)

    def test_snapshot_settings_can_be_resolved_from_local_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_file = root / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "CONTEXTFORGE_GITHUB_PROJECT_OWNER=example-owner",
                        "CONTEXTFORGE_GITHUB_REPO=example-owner/example-repo",
                        "CONTEXTFORGE_GITHUB_PROJECT_NUMBER=6",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            parsed = github_project6_sync.parse_env_file(env_file)

            with mock.patch.dict(github_project6_sync.os.environ, {}, clear=True):
                self.assertEqual(
                    "example-owner",
                    github_project6_sync.resolve_setting(
                        None,
                        env_name=github_project6_sync.ENV_OWNER,
                        env_file_values=parsed,
                    ),
                )
                self.assertEqual(
                    "example-owner/example-repo",
                    github_project6_sync.resolve_setting(
                        None,
                        env_name=github_project6_sync.ENV_REPO,
                        env_file_values=parsed,
                    ),
                )
                self.assertEqual(6, github_project6_sync.resolve_project_number(None, env_file_values=parsed))

    def test_owner_and_repo_are_required_without_cli_or_env(self) -> None:
        with mock.patch.dict(github_project6_sync.os.environ, {}, clear=True):
            with self.assertRaises(github_project6_sync.ProjectSyncError):
                github_project6_sync.resolve_setting(
                    None,
                    env_name=github_project6_sync.ENV_OWNER,
                    env_file_values={},
                )

    def test_generated_local_json_boundary_rejects_non_ignored_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = github_project6_sync.ensure_generated_local_json(
                Path("generated/project6-snapshot.local.json"),
                repo_root=root,
            )
            self.assertEqual(root / "generated" / "project6-snapshot.local.json", valid)

            with self.assertRaises(ValueError):
                github_project6_sync.ensure_generated_local_json(Path("generated/project6-snapshot.json"), repo_root=root)

            with self.assertRaises(ValueError):
                github_project6_sync.ensure_generated_local_json(Path("run/project6-snapshot.local.json"), repo_root=root)

    def test_plan_resolves_single_select_ids_and_suppresses_no_ops(self) -> None:
        snapshot = {
            "query": "-status:Done",
            "owner": "example-owner",
            "project_number": 6,
            "repo": "example-owner/example-repo",
            "project": {"id": "PVT_project"},
            "fields": {
                "Agent state": {
                    "id": "field_agent",
                    "type": "ProjectV2SingleSelectField",
                    "options_by_name": {"Ready": "opt_ready", "Active": "opt_active"},
                },
                "Dependency clues": {
                    "id": "field_deps",
                    "type": "ProjectV2Field",
                    "options_by_name": {},
                },
            },
            "items": [
                {
                    "id": "item_166",
                    "agent state": "Ready",
                    "content": {"number": 166, "title": "Add low-quota GitHub Project 6 sync helper"},
                }
            ],
        }

        noop_plan = github_project6_sync.build_plan(
            snapshot=snapshot,
            assignments=[github_project6_sync.parse_assignment("#166=Ready", default_field="Agent state")],
            now=1234,
        )
        self.assertEqual(1, noop_plan["summary"]["no_op"])
        self.assertEqual(0, noop_plan["summary"]["to_apply"])

        active_plan = github_project6_sync.build_plan(
            snapshot=snapshot,
            assignments=[github_project6_sync.parse_assignment("#166=Active", default_field="Agent state")],
            now=1235,
        )
        mutation = active_plan["mutations"][0]
        self.assertFalse(mutation["no_op"])
        self.assertEqual("Add low-quota GitHub Project 6 sync helper", mutation["title"])
        self.assertEqual("item_166", mutation["item_id"])
        self.assertEqual("field_agent", mutation["field_id"])
        self.assertEqual({"singleSelectOptionId": "opt_active"}, mutation["value"])

        text_plan = github_project6_sync.build_plan(
            snapshot=snapshot,
            assignments=[
                github_project6_sync.parse_assignment(
                    "#166:Dependency clues=Depends on Project #6 schema cache.",
                )
            ],
            now=1236,
        )
        text_mutation = text_plan["mutations"][0]
        self.assertEqual("update_text", text_mutation["operation"])
        self.assertEqual("field_deps", text_mutation["field_id"])
        self.assertEqual({"text": "Depends on Project #6 schema cache."}, text_mutation["value"])

    def test_field_assignment_supports_draft_titles_with_colons(self) -> None:
        assignment = github_project6_sync.parse_assignment(
            "Roadmap: Operator productization:Dependency clues=#159 first."
        )

        self.assertEqual("Roadmap: Operator productization", assignment["target"])
        self.assertEqual("Dependency clues", assignment["field"])
        self.assertEqual("#159 first.", assignment["desired"])

    def test_apply_defaults_to_dry_run_and_needs_confirm_for_graphql(self) -> None:
        plan = {
            "project": {"id": "PVT_project"},
            "owner": "example-owner",
            "project_number": 6,
            "mutations": [
                {
                    "target": "#166",
                    "title": "Add low-quota GitHub Project 6 sync helper",
                    "item_id": "item_166",
                    "field_id": "field_agent",
                    "no_op": False,
                    "value": {"singleSelectOptionId": "opt_active"},
                }
            ],
        }
        runner = FakeRunner()

        dry_run = github_project6_sync.apply_plan(plan=plan, confirm=False, batch_size=5, runner=runner)
        self.assertTrue(dry_run["dry_run"])
        self.assertEqual([], runner.calls)

        applied = github_project6_sync.apply_plan(plan=plan, confirm=True, batch_size=1, runner=runner)
        self.assertFalse(applied["dry_run"])
        self.assertEqual(1, applied["applied"])
        self.assertEqual(["gh", "api", "graphql"], runner.calls[0][:3])
        self.assertIn("updateProjectV2ItemFieldValue", runner.calls[0][-1])
        self.assertIn("singleSelectOptionId", runner.calls[0][-1])
        self.assertEqual("Add low-quota GitHub Project 6 sync helper", applied["targeted_readback"][0]["query"])
        self.assertEqual(1, applied["targeted_readback"][0]["result"]["totalCount"])
        self.assertEqual(1, applied["rate_limit"]["graphql_query"]["cost"])
        self.assertIn(["gh", "api", "rate_limit", "--jq", "{core:.resources.core, graphql:.resources.graphql}"], runner.calls)


if __name__ == "__main__":
    unittest.main()
