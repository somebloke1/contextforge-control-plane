"""Shared redaction helpers for ContextForge client-harness evidence."""

from __future__ import annotations

import os
import re
from typing import Any


REDACTION = "[REDACTED_CONTEXTFORGE_SECRET]"

SECRET_KEY_RE = re.compile(
    r"(?ix)"
    r"(?:"
    r"api[_-]?key|"
    r"access[_-]?token|"
    r"auth[_-]?token|"
    r"bearer[_-]?token|"
    r"contextforge[_-]?bearer[_-]?token|"
    r"client[_-]?secret|"
    r"credential|"
    r"jwt|"
    r"password|"
    r"private[_-]?key|"
    r"refresh[_-]?token|"
    r"secret|"
    r"(?:^|[_-])token(?:[_-]|$)"
    r")"
)

TOKEN_ID_RE = re.compile(r"(?i)(?:^|[_-])token[_-]?id$")
SAFE_SECRET_METADATA_KEYS = frozenset(
    {
        "credential_boundary",
        "credentialboundary",
        "credential_required",
        "credentialrequired",
        "credential_scope",
        "credential_scope_id",
        "credentialscope",
        "credentialscopeid",
        "credential_scoped",
        "credentialscoped",
        "credential_state",
        "credentialstate",
        "credential_status",
        "credentialstatus",
    }
)
ENV_ASSIGNMENT_RE = re.compile(
    r"(?P<prefix>\b(?P<key>[A-Za-z_][A-Za-z0-9_./-]*)\s*[:=]\s*)"
    r"(?P<quote>['\"]?)"
    r"(?P<value>[^\s,'\"}>\]]+)"
)
JSON_SECRET_RE = re.compile(
    r"(?P<prefix>[\"'](?P<key>[^\"']+)[\"']\s*:\s*)"
    r"(?P<quote>[\"'])"
    r"(?P<value>.*?)(?P=quote)"
)
BEARER_RE = re.compile(
    r"(?P<prefix>\bAuthorization\s*[:=]\s*Bearer\s+|\bAuthorization\s*[:=]\s*|\bBearer\s+)"
    r"(?P<token>[A-Za-z0-9._~+/=-]{8,})",
    flags=re.IGNORECASE,
)


def secret_key(key: str) -> bool:
    normalized = key.strip().strip("\"'").replace(".", "_").replace("-", "_").lower()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    if normalized in SAFE_SECRET_METADATA_KEYS or compact in SAFE_SECRET_METADATA_KEYS:
        return False
    if TOKEN_ID_RE.search(normalized):
        return False
    return bool(SECRET_KEY_RE.search(normalized))


def explicit_values() -> list[str]:
    values = []
    for raw in os.environ.get("CONTEXTFORGE_REDACT_VALUES", "").splitlines():
        value = raw.strip()
        if len(value) >= 4:
            values.append(value)
    for name, value in os.environ.items():
        if secret_key(name) and value and len(value) >= 4:
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def redact_line(line: str, raw_values: list[str] | None = None) -> str:
    raw_values = explicit_values() if raw_values is None else raw_values
    for value in raw_values:
        line = line.replace(value, REDACTION)

    def replace_bearer(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{REDACTION}"

    line = BEARER_RE.sub(replace_bearer, line)

    def replace_json(match: re.Match[str]) -> str:
        if not secret_key(match.group("key")):
            return match.group(0)
        return f"{match.group('prefix')}{match.group('quote')}{REDACTION}{match.group('quote')}"

    line = JSON_SECRET_RE.sub(replace_json, line)

    def replace_assignment(match: re.Match[str]) -> str:
        if not secret_key(match.group("key")):
            return match.group(0)
        return f"{match.group('prefix')}{match.group('quote')}{REDACTION}{match.group('quote')}"

    return ENV_ASSIGNMENT_RE.sub(replace_assignment, line)


def redact_text(text: str) -> str:
    raw_values = explicit_values()
    return "".join(redact_line(line, raw_values) for line in text.splitlines(keepends=True))


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if secret_key(str(key)) and isinstance(item, str):
                redacted[key] = REDACTION
            else:
                redacted[key] = redact_value(item)
        return redacted
    return value
