#!/usr/bin/env python3
"""Lint readiness and evidence claims for overbroad ContextForge proof.

This helper is pure and project-local: it reads text supplied by callers and
returns structured diagnostics. It does not inspect runtime services, mutate
state, or validate whether cited evidence actually exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


LINTER_VERSION = 1
SCHEMA_URI = "contextforge://control-plane/schemas/readiness-claim-lint/v1"

CANONICAL_SURFACE_LABELS = frozenset(
    {
        "legacy_live_read_only",
        "contextforge_dev_docker",
        "pi_client_docker",
        "opencode_client_docker",
        "local_source",
        "target_client",
        "generated_run_evidence",
    }
)

READINESS_TERMS = (
    "ready",
    "readiness",
    "validated",
    "validation",
    "verified",
    "complete",
    "passed",
    "active",
    "source_ready",
    "backend_ready",
    "contextforge_ready",
    "target_client_ready",
    "presumed_working",
)

EVIDENCE_TERMS = (
    "based on",
    "because",
    "evidence",
    "proof",
    "readback",
    "probe",
    "trace",
    "artifact",
    "command",
    "smoke",
    "health",
    "listener",
    "test",
    "unittest",
)

BOUNDARY_TERMS = (
    "is not",
    "does not prove",
    "cannot prove",
    "not target_client_ready",
    "not current",
    "historical",
    "comparison-only",
    "missing proof",
    "boundary",
    "pending",
)

READINESS_RE = re.compile(
    r"\b("
    + "|".join(re.escape(term) for term in READINESS_TERMS)
    + r")\b",
    re.IGNORECASE,
)
READINESS_CLAIM_RE = re.compile(
    r"\b("
    r"is|are|was|were|remains?|became|becomes|marks?|marked|declares?|declared"
    r")\b.{0,120}\b("
    + "|".join(re.escape(term) for term in READINESS_TERMS)
    + r")\b",
    re.IGNORECASE | re.DOTALL,
)
EVIDENCE_RE = re.compile(
    r"\b("
    + "|".join(re.escape(term) for term in EVIDENCE_TERMS)
    + r")\b",
    re.IGNORECASE,
)
SURFACE_RE = re.compile(r"\b(" + "|".join(re.escape(label) for label in sorted(CANONICAL_SURFACE_LABELS)) + r")\b")
HISTORICAL_RE = re.compile(
    r"\b(historical|comparison-only|comparison evidence|older evidence|previous evidence|stale)\b",
    re.IGNORECASE,
)
CURRENT_PROMOTION_RE = re.compile(
    r"\b("
    r"is|are|was|were|proves?|proved|shows?|showed|demonstrates?|demonstrated|validates?|validated"
    r")\b.{0,120}\b(ready|readiness|validated|verified|complete|passed|active|target_client_ready|contextforge_ready|backend_ready)\b",
    re.IGNORECASE | re.DOTALL,
)
TARGET_CLIENT_RE = re.compile(
    r"\b(target[-_ ]client|target_client_ready|client[- ]visible|Pi|OpenCode|host Pi|client readiness)\b",
    re.IGNORECASE,
)
BACKEND_ONLY_RE = re.compile(
    r"\b(backend[-_ ]only|backend health|backend_ready|listener|socket|upstream backend|direct backend|API probe|health check)\b",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(
    r"("
    r"`[^`]+`|"
    r"\b(?:docs|tests|scripts|docker|server-instances|run|generated)/[A-Za-z0-9_./#:-]+|"
    r"\b[A-Za-z0-9_.-]+\.local\.jsonl?\b|"
    r"\b[A-Za-z0-9_.-]+\.(?:json|jsonl|md|py|sh|txt)\b|"
    r"\b(?:issue|comment|PR|pull request)\s*#?\d+\b|"
    r"#\d+\b|"
    r"\bsha256:[0-9a-f]{16,64}\b|"
    r"\b(?:PYTHONDONTWRITEBYTECODE|git|bash|python|uv|docker|gh|curl|systemctl|ss)\b"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    source: str
    line: int
    message: str
    excerpt: str


@dataclass(frozen=True)
class TextBlock:
    start_line: int
    text: str


def lint_text(text: str, *, source: str = "<text>") -> list[dict[str, Any]]:
    """Return structured diagnostics for readiness/evidence overclaims."""

    diagnostics: list[Diagnostic] = []
    for block in _prose_blocks(text):
        normalized = _normalize(block.text)
        if not normalized or _is_meta_guardrail_block(normalized):
            continue

        has_readiness_claim = _has_readiness_claim(normalized)
        has_evidence = bool(EVIDENCE_RE.search(normalized))
        has_surface = bool(SURFACE_RE.search(normalized))
        has_reference = bool(REFERENCE_RE.search(normalized))
        has_boundary = _has_boundary(normalized)

        if has_readiness_claim and not has_reference and not has_boundary:
            diagnostics.append(
                _diagnostic(
                    code="readiness_claim_missing_evidence",
                    source=source,
                    line=block.start_line,
                    message="Readiness/status claim lacks an evidence reference, command, artifact, issue, or file path.",
                    text=normalized,
                )
            )

        if has_readiness_claim and has_evidence and not has_surface and not has_boundary:
            diagnostics.append(
                _diagnostic(
                    code="evidence_missing_surface_label",
                    source=source,
                    line=block.start_line,
                    message="Evidence-backed readiness claim lacks a canonical exercised surface label.",
                    text=normalized,
                )
            )

        if _promotes_historical_evidence(normalized) and not _has_historical_boundary(normalized):
            diagnostics.append(
                _diagnostic(
                    code="historical_evidence_current_readiness",
                    source=source,
                    line=block.start_line,
                    message="Historical, stale, or comparison evidence is phrased as current readiness proof.",
                    text=normalized,
                )
            )

        if _promotes_backend_to_target_client(normalized):
            diagnostics.append(
                _diagnostic(
                    code="backend_only_target_client_overclaim",
                    source=source,
                    line=block.start_line,
                    message="Backend-only proof is claimed as target-client-visible readiness.",
                    text=normalized,
                )
            )

    return [asdict(item) for item in diagnostics]


def lint_files(paths: Sequence[Path]) -> dict[str, Any]:
    """Lint files and return a stable report."""

    files: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        source = str(path)
        file_diagnostics = lint_text(text, source=source)
        files.append({"path": source, "diagnostic_count": len(file_diagnostics)})
        diagnostics.extend(file_diagnostics)

    return {
        "schema_version": LINTER_VERSION,
        "schema_uri": SCHEMA_URI,
        "status": "failed" if diagnostics else "passed",
        "diagnostic_count": len(diagnostics),
        "files": files,
        "diagnostics": diagnostics,
    }


def _prose_blocks(text: str) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    current: list[str] = []
    start_line: int | None = None
    in_fence = False

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if current:
                blocks.append(TextBlock(start_line=start_line or line_number, text="\n".join(current)))
                current = []
                start_line = None
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped:
            if current:
                blocks.append(TextBlock(start_line=start_line or line_number, text="\n".join(current)))
                current = []
                start_line = None
            continue
        if start_line is None:
            start_line = line_number
        current.append(line)

    if current:
        blocks.append(TextBlock(start_line=start_line or 1, text="\n".join(current)))
    return blocks


def _is_meta_guardrail_block(text: str) -> bool:
    lower = text.lower()
    if lower.startswith("|"):
        return True
    if lower.startswith("#"):
        return True
    if lower.startswith("this document defines"):
        return True
    if lower.startswith("readiness claims must"):
        return True
    if lower.startswith("when reporting readiness"):
        return True
    if lower.startswith("every readiness claim must"):
        return True
    if lower.startswith("do not claim:") or lower.startswith("examples:"):
        return True
    if lower.startswith("- `") and " from `" in lower:
        return True
    if "required evidence" in lower and "not enough" in lower:
        return True
    return False


def _has_boundary(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in BOUNDARY_TERMS)


def _has_historical_boundary(text: str) -> bool:
    lower = text.lower()
    return any(
        term in lower
        for term in (
            "does not prove current",
            "cannot prove current",
            "not current",
            "historical context",
            "comparison-only",
            "must be refreshed",
            "refresh boundary",
            "not target_client_ready",
            "not contextforge_ready",
            "not verified",
        )
    )


def _promotes_historical_evidence(text: str) -> bool:
    return any(
        HISTORICAL_RE.search(sentence) and CURRENT_PROMOTION_RE.search(sentence)
        for sentence in _sentences(text)
    )


def _promotes_backend_to_target_client(text: str) -> bool:
    if not (BACKEND_ONLY_RE.search(text) and TARGET_CLIENT_RE.search(text)):
        return False
    if re.search(
        r"\bnot\s+(?:target[-_ ]client|target_client_ready|client[- ]visible|Pi|OpenCode|host Pi)",
        text,
        re.IGNORECASE,
    ):
        return False
    if re.search(r"\bdoes not prove\b|\bcannot prove\b|\binsufficient\b|\bmissing\b", text, re.IGNORECASE):
        return False
    return bool(CURRENT_PROMOTION_RE.search(text) or _has_readiness_claim(text))


def _has_readiness_claim(text: str) -> bool:
    if READINESS_CLAIM_RE.search(text):
        return True
    return bool(
        re.search(
            r"\b(proves?|proved|shows?|showed|demonstrates?|demonstrated|validates?|validated)\b",
            text,
            re.IGNORECASE,
        )
        and READINESS_RE.search(text)
    )


def _sentences(text: str) -> Iterable[str]:
    return (item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip())


def _diagnostic(*, code: str, source: str, line: int, message: str, text: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity="warning",
        source=source,
        line=line,
        message=message,
        excerpt=_excerpt(text),
    )


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _excerpt(text: str, *, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Text or Markdown files to lint. Reads stdin when omitted.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.paths:
        report = lint_files(args.paths)
    else:
        diagnostics = lint_text(sys.stdin.read(), source="<stdin>")
        report = {
            "schema_version": LINTER_VERSION,
            "schema_uri": SCHEMA_URI,
            "status": "failed" if diagnostics else "passed",
            "diagnostic_count": len(diagnostics),
            "files": [{"path": "<stdin>", "diagnostic_count": len(diagnostics)}],
            "diagnostics": diagnostics,
        }

    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 1 if report["diagnostics"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
