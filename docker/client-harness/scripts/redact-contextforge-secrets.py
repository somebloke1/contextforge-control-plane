#!/usr/bin/env python3
"""Redact ContextForge secret material from harness transcript streams."""

from __future__ import annotations

import os
import re
import sys


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
    r"secret"
    r")"
)

TOKEN_ID_RE = re.compile(r"(?i)(?:^|[_-])token[_-]?id$")
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
    normalized = key.strip().strip("\"'").replace(".", "_")
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


def redact_line(line: str, raw_values: list[str]) -> str:
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


def main() -> int:
    raw_values = explicit_values()
    for line in sys.stdin:
        sys.stdout.write(redact_line(line, raw_values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
