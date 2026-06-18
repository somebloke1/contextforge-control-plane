#!/usr/bin/env python3
"""Summarize exact advertised model identity from OpenAI-compatible model lists."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from typing import Any


REPORT_SCHEMA = "contextforge://control-plane/client-model-identity/v1"


def _string_values(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
        elif isinstance(value, Mapping):
            model_id = value.get("id") or value.get("name") or value.get("model")
            if isinstance(model_id, str) and model_id.strip():
                result.append(model_id.strip())
    return result


def advertised_model_ids(payload: Any) -> list[str]:
    """Extract advertised model IDs from common OpenAI-compatible shapes."""

    if isinstance(payload, Mapping):
        candidates: list[str] = []
        data = payload.get("data")
        models = payload.get("models")
        if isinstance(data, list):
            candidates.extend(_string_values(data))
        if isinstance(models, list):
            candidates.extend(_string_values(models))
        if isinstance(payload.get("id"), str):
            candidates.append(str(payload["id"]).strip())
        return sorted({candidate for candidate in candidates if candidate})
    if isinstance(payload, list):
        return sorted(set(_string_values(payload)))
    return []


def build_identity_report(
    *,
    expected_model_id: str,
    payload: Any,
    surface: str,
    client: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    advertised = advertised_model_ids(payload)
    exact_match = expected_model_id in advertised
    if exact_match:
        status = "current"
        reason = "expected model id is advertised by the endpoint"
    elif advertised:
        status = "stale"
        reason = "expected model id is absent from advertised endpoint models"
    else:
        status = "unverified"
        reason = "endpoint response did not contain advertised model ids"

    return {
        "schema": REPORT_SCHEMA,
        "surface": surface,
        "client": client or "unspecified",
        "base_url": base_url or "unspecified",
        "expected_model_id": expected_model_id,
        "advertised_model_ids": advertised,
        "exact_match": exact_match,
        "status": status,
        "reason": reason,
        "non_actions": [
            "no model server install",
            "no model server replacement",
            "no client/global config mutation",
            "no runtime secret persistence",
        ],
    }


def _load_payload(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"_parse_error": f"{type(exc).__name__}: {exc}"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a client model identity evidence report")
    parser.add_argument("--expected-model-id", required=True)
    parser.add_argument("--surface", required=True)
    parser.add_argument("--client", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="Exit non-zero when the advertised models do not contain the expected id.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = _load_payload(sys.stdin.read())
    report = build_identity_report(
        expected_model_id=args.expected_model_id,
        payload=payload,
        surface=args.surface,
        client=args.client,
        base_url=args.base_url,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.fail_on_stale and report["status"] == "stale":
        return 2
    if args.fail_on_stale and report["status"] == "unverified":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
