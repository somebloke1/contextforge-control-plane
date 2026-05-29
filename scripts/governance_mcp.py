#!/usr/bin/env python3
"""MCP server exposing governance ledger CRUD tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

try:
    from governance_registry import (
        EntryStatus,
        create_entry,
        delete_entry,
        error_result,
        list_entries,
        read_entry,
        update_entry,
    )
except ModuleNotFoundError:
    from tools.governance_registry import (
        EntryStatus,
        create_entry,
        delete_entry,
        error_result,
        list_entries,
        read_entry,
        update_entry,
    )


server = FastMCP("mentality")


@server.tool()
def governance_list(repo: str, ledger: str, status: EntryStatus | None = None) -> dict[str, Any]:
    """List entries in a repository-local governance ledger."""
    try:
        return list_entries(repo, ledger, status=status)
    except Exception as exc:
        return error_result(exc)


@server.tool()
def governance_read(repo: str, ledger: str, id: str) -> dict[str, Any]:
    """Read one entry from a repository-local governance ledger."""
    try:
        return read_entry(repo, ledger, id)
    except Exception as exc:
        return error_result(exc)


@server.tool()
def governance_create(
    repo: str,
    ledger: str,
    title: str,
    body: str = "",
    status: EntryStatus | None = None,
    tags: str = "none",
    id: str | None = None,
) -> dict[str, Any]:
    """Create one entry in a repository-local governance ledger."""
    try:
        return create_entry(
            repo,
            ledger,
            title=title,
            body=body,
            status=status,
            tags=tags,
            entry_id=id,
        )
    except Exception as exc:
        return error_result(exc)


@server.tool()
def governance_update(
    repo: str,
    ledger: str,
    id: str,
    title: str | None = None,
    body: str | None = None,
    status: EntryStatus | None = None,
    tags: str | None = None,
) -> dict[str, Any]:
    """Update one entry in a repository-local governance ledger."""
    try:
        return update_entry(
            repo,
            ledger,
            entry_id=id,
            title=title,
            body=body,
            status=status,
            tags=tags,
        )
    except Exception as exc:
        return error_result(exc)


@server.tool()
def governance_delete(repo: str, ledger: str, id: str) -> dict[str, Any]:
    """Delete one entry from a repository-local governance ledger."""
    try:
        return delete_entry(repo, ledger, id)
    except Exception as exc:
        return error_result(exc)


if __name__ == "__main__":
    server.run()
