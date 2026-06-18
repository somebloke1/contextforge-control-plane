#!/usr/bin/env python3
"""Low-quota GitHub Project #6 coordination helper.

The helper is intentionally read-mostly. Snapshot and plan commands write only
ignored ``generated/*.local.json`` artifacts by default. The apply command is a
dry run unless ``--confirm`` is provided.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ENV_OWNER = "CONTEXTFORGE_GITHUB_PROJECT_OWNER"
ENV_REPO = "CONTEXTFORGE_GITHUB_REPO"
ENV_PROJECT_NUMBER = "CONTEXTFORGE_GITHUB_PROJECT_NUMBER"
DEFAULT_PROJECT_NUMBER = 6
DEFAULT_QUERY = "-status:Done"
DEFAULT_LIMIT = 80
DEFAULT_TTL_SECONDS = 900
DEFAULT_CACHE_PATH = Path("generated/project6-cache.local.json")
DEFAULT_SNAPSHOT_PATH = Path("generated/project6-snapshot.local.json")
DEFAULT_PLAN_PATH = Path("generated/project6-plan.local.json")

SINGLE_SELECT_FIELD_TYPES = {"ProjectV2SingleSelectField"}


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class ProjectSyncError(RuntimeError):
    """Raised for invalid helper input or failed GitHub commands."""


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in {ENV_OWNER, ENV_REPO, ENV_PROJECT_NUMBER}:
            values[key] = value
    return values


def resolve_setting(
    explicit: str | None,
    *,
    env_name: str,
    env_file_values: Mapping[str, str],
    default: str | None = None,
) -> str:
    if explicit:
        return explicit
    if os.environ.get(env_name):
        return str(os.environ[env_name])
    if env_file_values.get(env_name):
        return str(env_file_values[env_name])
    if default is not None:
        return default
    raise ProjectSyncError(
        f"missing required setting {env_name}; pass the CLI option, export {env_name}, "
        "or place it in the local .env file"
    )


def resolve_project_number(explicit: int | None, *, env_file_values: Mapping[str, str]) -> int:
    if explicit is not None:
        return explicit
    raw = os.environ.get(ENV_PROJECT_NUMBER) or env_file_values.get(ENV_PROJECT_NUMBER)
    if raw:
        try:
            return int(raw)
        except ValueError as exc:
            raise ProjectSyncError(f"{ENV_PROJECT_NUMBER} must be an integer: {raw}") from exc
    return DEFAULT_PROJECT_NUMBER


def run_command(args: Sequence[str], *, cwd: Path | None = None, check: bool = True) -> CommandResult:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = CommandResult(list(args), completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        raise ProjectSyncError(format_command_failure(result))
    return result


def format_command_failure(result: CommandResult) -> str:
    return (
        f"command failed with exit {result.returncode}: {' '.join(result.args)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def parse_json_output(result: CommandResult) -> Any:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProjectSyncError(f"command did not return JSON: {' '.join(result.args)}") from exc


def read_rate_limit_evidence(runner=run_command) -> dict[str, Any]:
    rest = parse_json_output(
        runner(["gh", "api", "rate_limit", "--jq", "{core:.resources.core, graphql:.resources.graphql}"])
    )
    graphql = parse_json_output(
        runner(["gh", "api", "graphql", "-f", "query=query { rateLimit { cost remaining resetAt } }"])
    )
    graphql_rate = graphql.get("data", {}).get("rateLimit") if isinstance(graphql, Mapping) else None
    return {
        "rest": rest,
        "graphql_query": graphql_rate or graphql,
    }


def normalize_field_key(name: str) -> str:
    return " ".join(name.strip().lower().split())


def normalize_target(target: str) -> str:
    stripped = target.strip()
    if stripped.startswith("#"):
        stripped = stripped[1:]
    return stripped


def ensure_generated_local_json(path: Path, *, repo_root: Path) -> Path:
    candidate = (repo_root / path).resolve(strict=False) if not path.is_absolute() else path.resolve(strict=False)
    generated_root = (repo_root / "generated").resolve(strict=False)
    try:
        candidate.relative_to(generated_root)
    except ValueError as exc:
        raise ValueError(f"local artifact must be under {generated_root}: {candidate}") from exc
    if not candidate.name.endswith(".local.json"):
        raise ValueError(f"local artifact must end with .local.json: {candidate}")
    return candidate


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cache_is_fresh(cache: Mapping[str, Any], *, ttl_seconds: int, now: int) -> bool:
    updated_at = cache.get("updated_at_epoch")
    if not isinstance(updated_at, int):
        return False
    return now - updated_at <= ttl_seconds


def build_project_schema(project: Mapping[str, Any], fields_payload: Mapping[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in fields_payload.get("fields", []):
        if not isinstance(field, Mapping):
            continue
        name = field.get("name")
        field_id = field.get("id")
        field_type = field.get("type")
        if not isinstance(name, str) or not isinstance(field_id, str):
            continue
        options_by_name: dict[str, str] = {}
        for option in field.get("options", []) or []:
            if isinstance(option, Mapping) and isinstance(option.get("name"), str) and isinstance(option.get("id"), str):
                options_by_name[option["name"]] = option["id"]
        fields[name] = {
            "id": field_id,
            "type": field_type,
            "options_by_name": options_by_name,
        }

    return {
        "project": {
            "id": project.get("id"),
            "number": project.get("number"),
            "owner": project.get("owner", {}).get("login") if isinstance(project.get("owner"), Mapping) else None,
            "title": project.get("title"),
        },
        "fields": fields,
    }


def refresh_schema_cache(
    *,
    owner: str,
    project_number: int,
    now: int,
    runner=run_command,
) -> dict[str, Any]:
    project = parse_json_output(
        runner(["gh", "project", "view", str(project_number), "--owner", owner, "--format", "json"])
    )
    fields = parse_json_output(
        runner(["gh", "project", "field-list", str(project_number), "--owner", owner, "--format", "json"])
    )
    schema = build_project_schema(project, fields)
    return {
        "schema_version": 1,
        "updated_at_epoch": now,
        "source": {
            "owner": owner,
            "project_number": project_number,
            "commands": [
                f"gh project view {project_number} --owner {owner} --format json",
                f"gh project field-list {project_number} --owner {owner} --format json",
            ],
        },
        **schema,
    }


def load_or_refresh_cache(
    *,
    owner: str,
    project_number: int,
    cache_path: Path,
    ttl_seconds: int,
    now: int,
    refresh: bool = False,
    runner=run_command,
) -> dict[str, Any]:
    if cache_path.exists() and not refresh:
        cache = read_json_file(cache_path)
        if isinstance(cache, Mapping) and cache_is_fresh(cache, ttl_seconds=ttl_seconds, now=now):
            return dict(cache)

    cache = refresh_schema_cache(owner=owner, project_number=project_number, now=now, runner=runner)
    write_json_file(cache_path, cache)
    return cache


def summarize_rest_issue(issue: Mapping[str, Any]) -> dict[str, Any]:
    pull_request = issue.get("pull_request")
    labels = issue.get("labels") if isinstance(issue.get("labels"), list) else []
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "type": "PullRequest" if isinstance(pull_request, Mapping) else "Issue",
        "html_url": issue.get("html_url"),
        "labels": [label.get("name") for label in labels if isinstance(label, Mapping) and label.get("name")],
        "updated_at": issue.get("updated_at"),
    }


def item_lookup_keys(item: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    content = item.get("content")
    if isinstance(content, Mapping):
        number = content.get("number")
        if isinstance(number, int):
            keys.append(str(number))
            keys.append(f"#{number}")
        title = content.get("title")
        if isinstance(title, str):
            keys.append(title)
    title = item.get("title")
    if isinstance(title, str):
        keys.append(title)
    return keys


def build_item_index(items: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        for key in item_lookup_keys(item):
            index[key] = item_id
    return index


def build_snapshot(
    *,
    owner: str,
    project_number: int,
    repo: str,
    query: str,
    limit: int,
    ttl_seconds: int,
    cache_path: Path,
    refresh_cache: bool,
    now: int,
    runner=run_command,
) -> dict[str, Any]:
    cache = load_or_refresh_cache(
        owner=owner,
        project_number=project_number,
        cache_path=cache_path,
        ttl_seconds=ttl_seconds,
        now=now,
        refresh=refresh_cache,
        runner=runner,
    )
    project_items = parse_json_output(
        runner(
            [
                "gh",
                "project",
                "item-list",
                str(project_number),
                "--owner",
                owner,
                "--format",
                "json",
                "--query",
                query,
                "--limit",
                str(limit),
            ]
        )
    )
    rest_issues = parse_json_output(runner(["gh", "api", f"repos/{repo}/issues?state=open&per_page=100"]))
    rate_limit = read_rate_limit_evidence(runner=runner)
    items = project_items.get("items", []) if isinstance(project_items, Mapping) else []
    normalized_items = [dict(item) for item in items if isinstance(item, Mapping)]
    snapshot = {
        "schema_version": 1,
        "created_at_epoch": now,
        "owner": owner,
        "project_number": project_number,
        "repo": repo,
        "query": query,
        "limit": limit,
        "schema_cache_path": str(cache_path),
        "project": cache.get("project", {}),
        "fields": cache.get("fields", {}),
        "item_ids_by_key": build_item_index(normalized_items),
        "items": normalized_items,
        "rest_issue_pr_summary": [
            summarize_rest_issue(issue) for issue in rest_issues if isinstance(issue, Mapping)
        ],
        "rate_limit": rate_limit,
        "commands": {
            "project_snapshot": f"gh project item-list {project_number} --owner {owner} --format json --query {query!r} --limit {limit}",
            "rest_issue_pr_substance": f"gh api repos/{repo}/issues?state=open&per_page=100",
            "rate_limit": "gh api rate_limit --jq '{core:.resources.core, graphql:.resources.graphql}'",
        },
        "non_actions": [
            "snapshot is read-only",
            "issue/PR substance is read through REST",
            "Project schema IDs are cached in generated local state",
        ],
    }
    return snapshot


def find_item(snapshot: Mapping[str, Any], target: str) -> Mapping[str, Any]:
    normalized = normalize_target(target)
    for item in snapshot.get("items", []):
        if not isinstance(item, Mapping):
            continue
        if normalized in {normalize_target(key) for key in item_lookup_keys(item)}:
            return item
    raise ProjectSyncError(f"target not found in snapshot items: {target}")


def current_field_value(item: Mapping[str, Any], field_name: str) -> Any:
    key = normalize_field_key(field_name)
    for candidate_key, value in item.items():
        if normalize_field_key(str(candidate_key)) == key:
            return value
    return None


def field_metadata(snapshot: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    fields = snapshot.get("fields", {})
    if not isinstance(fields, Mapping):
        raise ProjectSyncError("snapshot is missing fields metadata")
    for name, metadata in fields.items():
        if normalize_field_key(str(name)) == normalize_field_key(field_name) and isinstance(metadata, Mapping):
            return metadata
    raise ProjectSyncError(f"field not found in snapshot metadata: {field_name}")


def parse_assignment(raw: str, *, default_field: str | None = None) -> dict[str, str]:
    if "=" not in raw:
        raise ValueError(f"assignment must contain '=': {raw}")
    left, desired = raw.split("=", 1)
    if default_field is not None:
        target = left
        field = default_field
    else:
        if ":" not in left:
            raise ValueError(f"field assignment must use TARGET:FIELD=VALUE: {raw}")
        target, field = left.rsplit(":", 1)
    return {"target": target.strip(), "field": field.strip(), "desired": desired.strip()}


def build_mutation(snapshot: Mapping[str, Any], assignment: Mapping[str, str]) -> dict[str, Any]:
    item = find_item(snapshot, assignment["target"])
    item_id = item.get("id")
    if not isinstance(item_id, str):
        raise ProjectSyncError(f"target item is missing Project item id: {assignment['target']}")
    metadata = field_metadata(snapshot, assignment["field"])
    field_id = metadata.get("id")
    field_type = metadata.get("type")
    if not isinstance(field_id, str):
        raise ProjectSyncError(f"field is missing id: {assignment['field']}")
    current = current_field_value(item, assignment["field"])
    desired = assignment["desired"]
    content = item.get("content")
    title = content.get("title") if isinstance(content, Mapping) else item.get("title")
    mutation: dict[str, Any] = {
        "target": assignment["target"],
        "title": title,
        "item_id": item_id,
        "field": assignment["field"],
        "field_id": field_id,
        "field_type": field_type,
        "current": current,
        "desired": desired,
        "no_op": current == desired,
    }
    if field_type in SINGLE_SELECT_FIELD_TYPES:
        options = metadata.get("options_by_name", {})
        if not isinstance(options, Mapping) or desired not in options:
            raise ProjectSyncError(f"unknown option {desired!r} for field {assignment['field']}")
        mutation["value"] = {"singleSelectOptionId": options[desired]}
        mutation["operation"] = "update_single_select"
    else:
        mutation["value"] = {"text": desired}
        mutation["operation"] = "update_text"
    return mutation


def build_plan(
    *,
    snapshot: Mapping[str, Any],
    assignments: Sequence[Mapping[str, str]],
    output_path: Path | None = None,
    now: int,
) -> dict[str, Any]:
    mutations = [build_mutation(snapshot, assignment) for assignment in assignments]
    actionable = [mutation for mutation in mutations if not mutation["no_op"]]
    return {
        "schema_version": 1,
        "created_at_epoch": now,
        "source_snapshot": snapshot.get("query"),
        "project": snapshot.get("project", {}),
        "owner": snapshot.get("owner"),
        "project_number": snapshot.get("project_number"),
        "repo": snapshot.get("repo"),
        "dry_run_default": True,
        "output_path": str(output_path) if output_path else None,
        "mutations": mutations,
        "summary": {
            "requested": len(mutations),
            "no_op": len(mutations) - len(actionable),
            "to_apply": len(actionable),
        },
        "non_actions": [
            "plan does not mutate GitHub",
            "no-op Project field updates are suppressed before apply",
        ],
    }


def graphql_quote(value: str) -> str:
    return json.dumps(value)


def graphql_value(value: Mapping[str, Any]) -> str:
    if "singleSelectOptionId" in value:
        return "{singleSelectOptionId:" + graphql_quote(str(value["singleSelectOptionId"])) + "}"
    if "text" in value:
        return "{text:" + graphql_quote(str(value["text"])) + "}"
    raise ProjectSyncError(f"unsupported GraphQL Project value: {value}")


def build_graphql_mutation(project_id: str, mutations: Sequence[Mapping[str, Any]]) -> str:
    lines = ["mutation {"]
    for index, mutation in enumerate(mutations):
        value = mutation.get("value")
        if not isinstance(value, Mapping):
            raise ProjectSyncError(f"mutation is missing value: {mutation}")
        lines.append(
            "  u{index}: updateProjectV2ItemFieldValue(input:{{projectId:{project_id}, itemId:{item_id}, "
            "fieldId:{field_id}, value:{value}}}){{projectV2Item{{id}}}}".format(
                index=index,
                project_id=graphql_quote(project_id),
                item_id=graphql_quote(str(mutation["item_id"])),
                field_id=graphql_quote(str(mutation["field_id"])),
                value=graphql_value(value),
            )
        )
    lines.append("}")
    return "\n".join(lines)


def targeted_readback_query(mutations: Sequence[Mapping[str, Any]]) -> str:
    terms: list[str] = []
    for mutation in mutations:
        title = mutation.get("title")
        if isinstance(title, str) and title.strip():
            terms.append(title.strip())
        else:
            target = mutation.get("target")
            if isinstance(target, str) and target.strip():
                terms.append(target.strip())
    unique_terms = list(dict.fromkeys(terms))
    return " OR ".join(unique_terms)


def chunked(values: Sequence[Mapping[str, Any]], size: int) -> list[list[Mapping[str, Any]]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    return [list(values[index : index + size]) for index in range(0, len(values), size)]


def apply_plan(
    *,
    plan: Mapping[str, Any],
    confirm: bool,
    batch_size: int,
    runner=run_command,
) -> dict[str, Any]:
    mutations = [mutation for mutation in plan.get("mutations", []) if isinstance(mutation, Mapping) and not mutation.get("no_op")]
    project = plan.get("project", {})
    project_id = project.get("id") if isinstance(project, Mapping) else None
    if not isinstance(project_id, str):
        raise ProjectSyncError("plan project metadata is missing project id")
    owner = plan.get("owner")
    project_number = plan.get("project_number")
    if not confirm:
        return {
            "schema_version": 1,
            "dry_run": True,
            "confirmed": False,
            "mutations_to_apply": len(mutations),
            "commands": [],
            "non_actions": ["apply was not confirmed; no GitHub mutation was run"],
        }

    commands: list[dict[str, Any]] = []
    for batch in chunked(mutations, batch_size):
        query = build_graphql_mutation(project_id, batch)
        result = runner(["gh", "api", "graphql", "-f", f"query={query}"])
        commands.append(
            {
                "mutation_count": len(batch),
                "query": query,
                "returncode": result.returncode,
                "stdout": parse_json_output(result),
            }
        )

    readback = None
    readback_query = targeted_readback_query(mutations)
    if isinstance(owner, str) and isinstance(project_number, int) and readback_query:
        readback = parse_json_output(
            runner(
                [
                    "gh",
                    "project",
                    "item-list",
                    str(project_number),
                    "--owner",
                    owner,
                    "--format",
                    "json",
                    "--query",
                    readback_query,
                    "--limit",
                    str(max(20, len(mutations))),
                ]
            )
        )
    rate_limit = read_rate_limit_evidence(runner=runner)

    return {
        "schema_version": 1,
        "dry_run": False,
        "confirmed": True,
        "applied": len(mutations),
        "batch_size": batch_size,
        "commands": commands,
        "targeted_readback": {
            "query": readback_query,
            "result": readback,
        },
        "rate_limit": rate_limit,
        "non_actions": ["apply mutates only GitHub Project item fields listed in the plan"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help=(
            "Optional local env file for "
            f"{ENV_OWNER}, {ENV_REPO}, and {ENV_PROJECT_NUMBER}; defaults to .env."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot", help="Write a filtered Project #6 snapshot.")
    snapshot.add_argument("--owner", default=None, help=f"GitHub Project owner; defaults to {ENV_OWNER}.")
    snapshot.add_argument("--project", type=int, default=None, help=f"Project number; defaults to {ENV_PROJECT_NUMBER} or 6.")
    snapshot.add_argument("--repo", default=None, help=f"Repository nameWithOwner; defaults to {ENV_REPO}.")
    snapshot.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)
    snapshot.add_argument("--query", default=DEFAULT_QUERY)
    snapshot.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    snapshot.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    snapshot.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    snapshot.add_argument("--refresh-cache", action="store_true")
    snapshot.add_argument("--format", choices=["json"], default="json")

    plan = subparsers.add_parser("plan", help="Create a dry-run Project field update plan.")
    plan.add_argument("--from-cache", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    plan.add_argument("--output", type=Path, default=DEFAULT_PLAN_PATH)
    plan.add_argument("--set-agent-state", action="append", default=[])
    plan.add_argument("--set-field", action="append", default=[])
    plan.add_argument("--format", choices=["json"], default="json")

    apply = subparsers.add_parser("apply", help="Apply a Project field update plan; dry-run unless confirmed.")
    apply.add_argument("--plan", type=Path, default=DEFAULT_PLAN_PATH)
    apply.add_argument("--batch-size", type=int, default=5)
    apply.add_argument("--confirm", action="store_true")
    apply.add_argument("--output", type=Path, default=None)
    apply.add_argument("--format", choices=["json"], default="json")

    return parser


def cmd_snapshot(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve(strict=False)
    env_file = (repo_root / args.env_file).resolve(strict=False) if not args.env_file.is_absolute() else args.env_file
    env_file_values = parse_env_file(env_file)
    owner = resolve_setting(args.owner, env_name=ENV_OWNER, env_file_values=env_file_values)
    repo = resolve_setting(args.repo, env_name=ENV_REPO, env_file_values=env_file_values)
    project_number = resolve_project_number(args.project, env_file_values=env_file_values)
    cache_path = ensure_generated_local_json(args.cache, repo_root=repo_root)
    output_path = ensure_generated_local_json(args.output, repo_root=repo_root)
    payload = build_snapshot(
        owner=owner,
        project_number=project_number,
        repo=repo,
        query=args.query,
        limit=args.limit,
        ttl_seconds=args.ttl,
        cache_path=cache_path,
        refresh_cache=args.refresh_cache,
        now=int(time.time()),
    )
    write_json_file(output_path, payload)
    print(json.dumps({"output": str(output_path), "items": len(payload["items"]), "rate_limit": payload["rate_limit"]}))
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve(strict=False)
    input_path = ensure_generated_local_json(args.from_cache, repo_root=repo_root)
    output_path = ensure_generated_local_json(args.output, repo_root=repo_root)
    snapshot = read_json_file(input_path)
    assignments = [parse_assignment(raw, default_field="Agent state") for raw in args.set_agent_state]
    assignments.extend(parse_assignment(raw) for raw in args.set_field)
    if not assignments:
        raise ProjectSyncError("plan requires at least one --set-agent-state or --set-field assignment")
    payload = build_plan(snapshot=snapshot, assignments=assignments, output_path=output_path, now=int(time.time()))
    write_json_file(output_path, payload)
    print(json.dumps({"output": str(output_path), **payload["summary"]}))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve(strict=False)
    input_path = ensure_generated_local_json(args.plan, repo_root=repo_root)
    plan = read_json_file(input_path)
    result = apply_plan(plan=plan, confirm=args.confirm, batch_size=args.batch_size)
    if args.output:
        output_path = ensure_generated_local_json(args.output, repo_root=repo_root)
        write_json_file(output_path, result)
        print(json.dumps({"output": str(output_path), "confirmed": result["confirmed"]}))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "snapshot":
        return cmd_snapshot(args)
    if args.command == "plan":
        return cmd_plan(args)
    if args.command == "apply":
        return cmd_apply(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ProjectSyncError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
