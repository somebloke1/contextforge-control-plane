#!/usr/bin/env python3
"""Importable CRUD operations for repository-local governance ledgers."""

from __future__ import annotations

import datetime as dt
import re
from enum import StrEnum
from pathlib import Path
from typing import Any


class EntryStatus(StrEnum):
    """Finite status vocabulary for governance ledger entries."""

    OPEN = "open"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    PARKED = "parked"
    HONORED = "honored"
    ANSWERED = "answered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


VALID_STATUSES: tuple[str, ...] = tuple(status.value for status in EntryStatus)

LEDGERS: dict[str, tuple[str, str]] = {
    "tasks": ("TASKS.md", "task"),
    "abeyant-intentions": ("ABEYANT_INTENTIONS.md", "ai"),
    "decisions": ("DECISIONS.md", "dec"),
    "open-questions": ("OPEN_QUESTIONS.md", "oq"),
}

DEFAULT_STATUS_BY_LEDGER: dict[str, EntryStatus] = {
    "tasks": EntryStatus.OPEN,
    "abeyant-intentions": EntryStatus.PARKED,
    "decisions": EntryStatus.ACCEPTED,
    "open-questions": EntryStatus.OPEN,
}

LEDGER_STATUSES: dict[str, tuple[EntryStatus, ...]] = {
    "tasks": (
        EntryStatus.OPEN,
        EntryStatus.IN_PROGRESS,
        EntryStatus.BLOCKED,
        EntryStatus.COMPLETED,
        EntryStatus.SUPERSEDED,
    ),
    "abeyant-intentions": (
        EntryStatus.PARKED,
        EntryStatus.HONORED,
        EntryStatus.SUPERSEDED,
    ),
    "decisions": (
        EntryStatus.ACCEPTED,
        EntryStatus.REJECTED,
        EntryStatus.SUPERSEDED,
    ),
    "open-questions": (
        EntryStatus.OPEN,
        EntryStatus.BLOCKED,
        EntryStatus.ANSWERED,
        EntryStatus.SUPERSEDED,
    ),
}

ENTRY_RE = re.compile(
    r"<!-- governance-crud:start id=(?P<id>[^ ]+) -->\n"
    r"(?P<body>.*?)"
    r"<!-- governance-crud:end id=(?P=id) -->",
    re.DOTALL,
)


class GovernanceRegistryError(ValueError):
    """Raised when a governance registry operation cannot be completed."""


def normalize_repo(repo: str | Path) -> Path:
    return Path(repo).expanduser().resolve()


def ledger_path(repo: str | Path, ledger: str) -> Path:
    if ledger not in LEDGERS:
        valid = ", ".join(sorted(LEDGERS))
        raise GovernanceRegistryError(f"Unknown ledger '{ledger}'. Valid ledgers: {valid}")
    return normalize_repo(repo) / LEDGERS[ledger][0]


def status_values_for_ledger(ledger: str) -> tuple[str, ...]:
    if ledger not in LEDGER_STATUSES:
        valid = ", ".join(sorted(LEDGERS))
        raise GovernanceRegistryError(f"Unknown ledger '{ledger}'. Valid ledgers: {valid}")
    return tuple(status.value for status in LEDGER_STATUSES[ledger])


def normalize_status(status: EntryStatus | str) -> str:
    status_value = status.value if isinstance(status, EntryStatus) else str(status).strip().lower()
    if status_value not in VALID_STATUSES:
        valid = ", ".join(VALID_STATUSES)
        raise GovernanceRegistryError(f"Unknown status '{status_value}'. Valid statuses: {valid}")
    return status_value


def validate_status_for_ledger(ledger: str, status: EntryStatus | str) -> str:
    status_value = normalize_status(status)
    valid = status_values_for_ledger(ledger)
    if status_value not in valid:
        valid_text = ", ".join(valid)
        raise GovernanceRegistryError(
            f"Status '{status_value}' is not valid for ledger '{ledger}'. "
            f"Valid statuses: {valid_text}"
        )
    return status_value


def resolve_status_for_ledger(ledger: str, status: EntryStatus | str | None) -> str:
    return validate_status_for_ledger(ledger, status or DEFAULT_STATUS_BY_LEDGER[ledger])


def today() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().date().isoformat()


def read_text(path: Path) -> str:
    if not path.exists():
        return f"# {path.stem.replace('_', ' ').title()}\n\n"
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_entries(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for match in ENTRY_RE.finditer(text):
        body = match.group("body")
        title_match = re.search(r"^##\s+[^:]+:\s+(?P<title>.+)$", body, re.MULTILINE)
        status_match = re.search(r"^- Status:\s+(?P<status>.+)$", body, re.MULTILINE)
        updated_match = re.search(r"^- Updated:\s+(?P<updated>.+)$", body, re.MULTILINE)
        entries.append(
            {
                "id": match.group("id"),
                "title": title_match.group("title").strip() if title_match else "",
                "status": status_match.group("status").strip() if status_match else "",
                "updated": updated_match.group("updated").strip() if updated_match else "",
                "raw": match.group(0),
                "body": body.strip(),
            }
        )
    return entries


def next_id(entries: list[dict[str, str]], prefix: str) -> str:
    date = dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y%m%d")
    pattern = re.compile(rf"^{re.escape(prefix)}-{date}-(\d+)$")
    numbers = [
        int(match.group(1))
        for entry in entries
        if (match := pattern.match(entry["id"]))
    ]
    return f"{prefix}-{date}-{max(numbers, default=0) + 1:04d}"


def existing_field(body: str, field: str, default: str) -> str:
    match = re.search(rf"^- {re.escape(field)}:\s+(?P<value>.+)$", body, re.MULTILINE)
    return match.group("value").strip() if match else default


def body_without_header(entry_body: str) -> str:
    parts = entry_body.split("\n\n", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return ""


def render_entry(
    *,
    entry_id: str,
    ledger: str,
    repo: Path,
    title: str,
    body: str,
    status: str,
    tags: str,
    created: str,
    updated: str,
) -> str:
    body_text = body.strip() or "(No details recorded.)"
    return (
        f"<!-- governance-crud:start id={entry_id} -->\n"
        f"## {entry_id}: {title}\n\n"
        f"- Ledger: {ledger}\n"
        f"- Status: {status}\n"
        f"- Repository: {repo}\n"
        f"- Created: {created}\n"
        f"- Updated: {updated}\n"
        f"- Tags: {tags or 'none'}\n\n"
        f"{body_text}\n"
        f"<!-- governance-crud:end id={entry_id} -->"
    )


def public_entry(entry: dict[str, str], include_raw: bool = False) -> dict[str, str]:
    keys = ["id", "title", "status", "updated", "body"]
    result = {key: entry[key] for key in keys}
    if include_raw:
        result["raw"] = entry["raw"]
    return result


def list_entries(repo: str | Path, ledger: str, status: EntryStatus | str | None = None) -> dict[str, Any]:
    path = ledger_path(repo, ledger)
    status_filter = validate_status_for_ledger(ledger, status) if status is not None else None
    entries = parse_entries(read_text(path))
    if status_filter is not None:
        entries = [
            entry
            for entry in entries
            if entry["status"].strip().lower() == status_filter
        ]
    return {
        "ok": True,
        "path": str(path),
        "status_filter": status_filter,
        "entries": [public_entry(entry) for entry in entries],
    }


def read_entry(repo: str | Path, ledger: str, entry_id: str) -> dict[str, Any]:
    path = ledger_path(repo, ledger)
    for entry in parse_entries(read_text(path)):
        if entry["id"] == entry_id:
            return {
                "ok": True,
                "path": str(path),
                "entry": public_entry(entry, include_raw=True),
            }
    raise GovernanceRegistryError(f"Entry not found: {entry_id}")


def create_entry(
    repo: str | Path,
    ledger: str,
    title: str,
    body: str = "",
    status: EntryStatus | str | None = None,
    tags: str = "none",
    entry_id: str | None = None,
) -> dict[str, Any]:
    repo_path = normalize_repo(repo)
    path = ledger_path(repo_path, ledger)
    status_value = resolve_status_for_ledger(ledger, status)
    text = read_text(path).rstrip()
    entries = parse_entries(text)
    new_id = entry_id or next_id(entries, LEDGERS[ledger][1])
    if any(entry["id"] == new_id for entry in entries):
        raise GovernanceRegistryError(f"Entry already exists: {new_id}")
    rendered = render_entry(
        entry_id=new_id,
        ledger=ledger,
        repo=repo_path,
        title=title,
        body=body,
        status=status_value,
        tags=tags,
        created=today(),
        updated=today(),
    )
    write_text(path, f"{text}\n\n{rendered}\n")
    return read_entry(repo_path, ledger, new_id)


def update_entry(
    repo: str | Path,
    ledger: str,
    entry_id: str,
    title: str | None = None,
    body: str | None = None,
    status: EntryStatus | str | None = None,
    tags: str | None = None,
) -> dict[str, Any]:
    repo_path = normalize_repo(repo)
    path = ledger_path(repo_path, ledger)
    text = read_text(path)
    entries = parse_entries(text)
    for entry in entries:
        if entry["id"] != entry_id:
            continue
        replacement = render_entry(
            entry_id=entry_id,
            ledger=ledger,
            repo=repo_path,
            title=title if title is not None else entry["title"],
            body=body if body is not None else body_without_header(entry["body"]),
            status=validate_status_for_ledger(ledger, status) if status is not None else entry["status"],
            tags=tags if tags is not None else existing_field(entry["body"], "Tags", "none"),
            created=existing_field(entry["body"], "Created", today()),
            updated=today(),
        )
        write_text(path, text.replace(entry["raw"], replacement))
        return read_entry(repo_path, ledger, entry_id)
    raise GovernanceRegistryError(f"Entry not found: {entry_id}")


def delete_entry(repo: str | Path, ledger: str, entry_id: str) -> dict[str, Any]:
    repo_path = normalize_repo(repo)
    path = ledger_path(repo_path, ledger)
    text = read_text(path)
    entries = parse_entries(text)
    for entry in entries:
        if entry["id"] == entry_id:
            updated = text.replace(entry["raw"], "").replace("\n\n\n", "\n\n")
            write_text(path, updated)
            return {
                "ok": True,
                "path": str(path),
                "entry": public_entry(entry, include_raw=True),
                "deleted": entry_id,
            }
    raise GovernanceRegistryError(f"Entry not found: {entry_id}")


def error_result(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": str(exc)}
