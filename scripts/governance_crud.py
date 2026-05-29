#!/usr/bin/env python3
"""CLI wrapper for repository-local governance ledgers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from governance_registry import (
        LEDGERS,
        VALID_STATUSES,
        GovernanceRegistryError,
        create_entry,
        delete_entry,
        list_entries,
        read_entry,
        update_entry,
    )
except ModuleNotFoundError:
    from tools.governance_registry import (
        LEDGERS,
        VALID_STATUSES,
        GovernanceRegistryError,
        create_entry,
        delete_entry,
        list_entries,
        read_entry,
        update_entry,
    )


def body_from_args(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8").strip()
    return (args.body or "").strip()


def cmd_list(args: argparse.Namespace) -> int:
    result = list_entries(args.repo, args.ledger, status=args.status)
    entries = result["entries"]
    if not entries:
        if result["status_filter"]:
            print(f"No {result['status_filter']} entries in {result['path']}")
            return 0
        print(f"No entries in {result['path']}")
        return 0
    print("| ID | Status | Updated | Title |")
    print("| --- | --- | --- | --- |")
    for entry in entries:
        print(
            f"| {entry['id']} | {entry['status']} | {entry['updated']} | "
            f"{entry['title']} |"
        )
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    result = read_entry(args.repo, args.ledger, args.id)
    print(result["entry"]["raw"])
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    result = create_entry(
        args.repo,
        args.ledger,
        title=args.title,
        body=body_from_args(args),
        status=args.status,
        tags=args.tags,
        entry_id=args.id,
    )
    print(result["entry"]["id"])
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    result = update_entry(
        args.repo,
        args.ledger,
        entry_id=args.id,
        title=args.title,
        body=body_from_args(args) if (args.body or args.body_file) else None,
        status=args.status,
        tags=args.tags,
    )
    print(result["entry"]["id"])
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    result = delete_entry(args.repo, args.ledger, args.id)
    print(result["deleted"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Repository path to operate on")
    parser.add_argument("--ledger", required=True, choices=sorted(LEDGERS))
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--status", choices=VALID_STATUSES)
    list_parser.set_defaults(func=cmd_list)

    read = subparsers.add_parser("read")
    read.add_argument("--id", required=True)
    read.set_defaults(func=cmd_read)

    create = subparsers.add_parser("create")
    create.add_argument("--id")
    create.add_argument("--title", required=True)
    create.add_argument("--body")
    create.add_argument("--body-file")
    create.add_argument("--status", choices=VALID_STATUSES)
    create.add_argument("--tags", default="none")
    create.set_defaults(func=cmd_create)

    update = subparsers.add_parser("update")
    update.add_argument("--id", required=True)
    update.add_argument("--title")
    update.add_argument("--body")
    update.add_argument("--body-file")
    update.add_argument("--status", choices=VALID_STATUSES)
    update.add_argument("--tags")
    update.set_defaults(func=cmd_update)

    delete = subparsers.add_parser("delete")
    delete.add_argument("--id", required=True)
    delete.set_defaults(func=cmd_delete)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except GovernanceRegistryError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
