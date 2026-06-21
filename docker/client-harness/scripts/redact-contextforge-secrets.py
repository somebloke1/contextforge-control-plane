#!/usr/bin/env python3
"""Redact ContextForge secret material from harness transcript streams."""

from __future__ import annotations

import sys

from harness_redaction import explicit_values, redact_line


def main() -> int:
    raw_values = explicit_values()
    for line in sys.stdin:
        sys.stdout.write(redact_line(line, raw_values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
