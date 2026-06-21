#!/usr/bin/env python3
"""Probe Docker-successor upstream URLs from inside the ContextForge container."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_URI = "contextforge://diagnostics/docker-upstream-reachability/v1"
DEFAULT_CONTAINER = "contextforge-harness-contextforge-gateway-1"
DEFAULT_PYTHON = "/app/.venv/bin/python"


CONTAINER_PROBE = r"""
import json
import urllib.error
import urllib.request

payload = json.load(open(0))
rows = []
for item in payload["targets"]:
    url = item["target_upstream_url"]
    try:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": "application/json, text/event-stream"},
        )
        with urllib.request.urlopen(request, timeout=payload["timeout_seconds"]) as response:
            rows.append({
                **item,
                "reachable": True,
                "status": response.status,
                "content_type": response.headers.get("content-type"),
            })
    except urllib.error.HTTPError as exc:
        rows.append({
            **item,
            "reachable": True,
            "status": exc.code,
            "reason": exc.reason,
            "content_type": exc.headers.get("content-type"),
        })
    except Exception as exc:
        rows.append({
            **item,
            "reachable": False,
            "error": type(exc).__name__,
            "message": str(exc)[:200],
        })
print(json.dumps(rows, sort_keys=True))
"""


def read_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def target_rows(plan: dict[str, Any], requested_slugs: set[str] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for service in plan.get("services", []):
        slug = service.get("slug")
        url = service.get("target_upstream_url")
        if not isinstance(slug, str) or not isinstance(url, str):
            continue
        if requested_slugs and slug not in requested_slugs:
            continue
        rows.append(
            {
                "slug": slug,
                "target_upstream_url": url,
                "locality": service.get("locality"),
                "approval_state": service.get("approval_state"),
                "approval_blocked": bool(service.get("approval_blocked")),
                "docker_projection_required": bool(service.get("docker_projection_required")),
            }
        )
    return rows


def classify(row: dict[str, Any]) -> str:
    if not row.get("reachable"):
        return "unreachable"
    status = row.get("status")
    if isinstance(status, int) and 200 <= status < 500:
        return "http_reachable"
    return "reachable_with_unexpected_status"


def build_report(
    *,
    plan_path: Path,
    targets: list[dict[str, Any]],
    probe_rows: list[dict[str, Any]],
    container: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    services = [{**row, "reachability_class": classify(row)} for row in probe_rows]
    unreachable = sorted(row["slug"] for row in services if row["reachability_class"] == "unreachable")
    reachable = sorted(row["slug"] for row in services if row["reachability_class"] != "unreachable")
    return {
        "schema_uri": SCHEMA_URI,
        "mutation_performed": False,
        "plan_path": str(plan_path),
        "probe_origin": {
            "mode": "docker_exec",
            "container": container,
            "timeout_seconds": timeout_seconds,
        },
        "target_count": len(targets),
        "summary": {
            "reachable_services": reachable,
            "unreachable_services": unreachable,
            "host_gateway_unreachable_services": sorted(
                row["slug"]
                for row in services
                if row.get("locality") == "host_gateway_projection" and row["reachability_class"] == "unreachable"
            ),
        },
        "services": services,
        "non_actions": [
            "no ContextForge API calls",
            "no registry, prompt, resource, server, or gateway mutation",
            "no Docker container lifecycle mutation",
            "no service, process, or systemd mutation",
            "no secret values read or printed",
        ],
    }


def run_probe(
    *,
    plan_path: Path,
    requested_slugs: set[str] | None,
    container: str,
    python_path: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    plan = read_plan(plan_path)
    targets = target_rows(plan, requested_slugs)
    payload = {"timeout_seconds": timeout_seconds, "targets": targets}
    result = subprocess.run(
        ["docker", "exec", "-i", container, python_path, "-c", CONTAINER_PROBE],
        input=json.dumps(payload),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=max(20, int(timeout_seconds * max(1, len(targets))) + 10),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"docker exec failed with status {result.returncode}")
    return build_report(
        plan_path=plan_path,
        targets=targets,
        probe_rows=json.loads(result.stdout),
        container=container,
        timeout_seconds=timeout_seconds,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="Docker migration plan JSON.")
    parser.add_argument("--service", action="append", dest="services", help="Limit to one service slug; repeatable.")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--python", default=DEFAULT_PYTHON)
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_probe(
        plan_path=args.plan,
        requested_slugs=set(args.services or []) or None,
        container=args.container,
        python_path=args.python,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
