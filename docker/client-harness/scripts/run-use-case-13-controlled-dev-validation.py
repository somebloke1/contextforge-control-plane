#!/usr/bin/env python3
"""Assemble Use Case 13 controlled development validation evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def command_text(command: list[str]) -> str:
    return " ".join(command)


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
    required: bool = True,
    ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result: dict[str, Any] = {
        "command": command,
        "command_text": command_text(command),
        "cwd": str(cwd),
        "timeout_seconds": timeout,
        "required": required,
        "timeout": False,
    }
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=merged_env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result.update(
            {
                "returncode": 124,
                "timeout": True,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }
        )
    else:
        result.update(
            {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
    ledger.append(result)
    if required and (result["returncode"] != 0 or result["timeout"]):
        raise RuntimeError(f"required command failed: {result['command_text']}")
    return result


def run_with_retries(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str],
    attempts: int,
    ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        result = run(command, cwd=cwd, timeout=timeout, env=env, required=False, ledger=ledger)
        result["attempt"] = attempt
        if result["returncode"] == 0 and not result["timeout"]:
            return result
        last = result
        if attempt < attempts:
            run(
                [
                    str(env["PYTHON"]),
                    "-c",
                    "import time; time.sleep(3)",
                ],
                cwd=cwd,
                timeout=10,
                env=env,
                required=False,
                ledger=ledger,
            )
    assert last is not None
    raise RuntimeError(f"required command failed after {attempts} attempts: {command_text(command)}")


def parse_json_stdout(result: dict[str, Any]) -> Any:
    stdout = str(result.get("stdout") or "").strip()
    if not stdout:
        return None
    return json.loads(stdout)


def status(result: dict[str, Any], *, required: bool | None = None) -> dict[str, Any]:
    return {
        "returncode": result.get("returncode"),
        "timeout": bool(result.get("timeout")),
        "required": bool(result.get("required") if required is None else required),
    }


def artifact_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists() and path.is_file(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
    }


def latest_package(repo_root: Path, use_case: str, client: str) -> str:
    root = repo_root / "docker" / "client-harness" / "evidence" / use_case / client
    matches = sorted(root.glob(f"{client}-evaluation-package-*.md"))
    return str(matches[-1]) if matches else ""


def render_package(metadata: dict[str, Any], verifier: dict[str, Any], ledger: list[dict[str, Any]]) -> str:
    lines = [
        "# Use Case 13 Controlled Development Validation Evidence",
        "",
        "## Claim Boundary",
        "",
        "This package demonstrates controlled development validation surfaces. It does not replace semantic dialogue evaluation for ordinary use cases and does not claim live/legacy ContextForge mutation.",
        "",
        "## Metadata",
        "",
        "```json",
        json.dumps(metadata, indent=2, sort_keys=True),
        "```",
        "",
        "## Verifier",
        "",
        "```json",
        json.dumps(verifier, indent=2, sort_keys=True),
        "```",
        "",
        "## Command Ledger",
        "",
        "```json",
        json.dumps(ledger, indent=2, sort_keys=True),
        "```",
        "",
        "## Evaluator Instructions",
        "",
        "Review this package against `docs/use-cases/use-case-13/package.md`.",
        "Confirm the dev/client surfaces are isolated, evidence paths are sufficient, and claim boundaries are honest.",
        "If any selected dialogue use-case evidence is used as a readiness claim, verify that the cited package has non-Spark semantic evaluator acceptance.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args(argv)

    if args.timeout < 90:
        raise SystemExit("--timeout must be at least 90 seconds")

    repo_root = Path(__file__).resolve().parents[3]
    harness_root = repo_root / "docker" / "client-harness"
    contextforge_root = repo_root / "docker" / "contextforge-harness"
    python = repo_root / "run" / "test-venvs" / "project-init-workflow" / "bin" / "python"
    if not python.exists():
        raise SystemExit(f"missing current-worktree test venv python: {python}")
    if Path(sys.executable).resolve() != python.resolve():
        raise SystemExit(f"run with {python}, not {sys.executable}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = harness_root / "evidence" / "use-case-13"
    output_root.mkdir(parents=True, exist_ok=True)
    ledger: list[dict[str, Any]] = []
    command_statuses: dict[str, dict[str, Any]] = {}

    runtime_env = {
        "PYTHON": str(python),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    command_statuses["contextforge_auth_preflight"] = status(
        run(["scripts/ensure-env-auth.sh"], cwd=contextforge_root, timeout=60, env=runtime_env, required=not args.skip_runtime, ledger=ledger),
    )
    if not args.skip_runtime:
        command_statuses["contextforge_compose_up"] = status(
            run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(contextforge_root / "compose.yml"),
                    "up",
                    "-d",
                    "contextforge-gateway",
                    "mentality-transceiver",
                ],
                cwd=repo_root,
                timeout=300,
                env=runtime_env,
                ledger=ledger,
            )
        )
        command_statuses["contextforge_health_wait"] = status(
            run(
                [
                    str(python),
                    "-c",
                    (
                        "import sys,time,urllib.request;"
                        "url=sys.argv[1]; deadline=time.time()+float(sys.argv[2]); last=None\n"
                        "while time.time()<deadline:\n"
                        "    try:\n"
                        "        urllib.request.urlopen(url, timeout=5).read(); print('health_wait_status=passed'); raise SystemExit(0)\n"
                        "    except Exception as exc:\n"
                        "        last=exc; time.sleep(2)\n"
                        "print(f'health_wait_status=failed {last.__class__.__name__ if last else \"unknown\"}', file=sys.stderr); raise SystemExit(1)\n"
                    ),
                    "http://127.0.0.1:4445/health",
                    "120",
                ],
                cwd=repo_root,
                timeout=150,
                env=runtime_env,
                ledger=ledger,
            )
        )
        command_statuses["register_mentality_dev"] = status(
            run(
                [str(python), str(contextforge_root / "scripts" / "register_mentality_dev.py")],
                cwd=contextforge_root,
                timeout=180,
                env=runtime_env,
                ledger=ledger,
            )
        )
        command_statuses["probe_mentality_dev"] = status(
            run_with_retries(
                [str(python), str(contextforge_root / "scripts" / "probe-mentality-dev.py")],
                cwd=contextforge_root,
                timeout=180,
                env=runtime_env,
                attempts=4,
                ledger=ledger,
            )
        )
    else:
        command_statuses["contextforge_compose_up"] = {"returncode": 0, "timeout": False, "required": False}
        command_statuses["contextforge_health_wait"] = {"returncode": 0, "timeout": False, "required": False}
        command_statuses["register_mentality_dev"] = {"returncode": 0, "timeout": False, "required": False}
        command_statuses["probe_mentality_dev"] = {"returncode": 0, "timeout": False, "required": False}

    clients: dict[str, dict[str, Any]] = {}
    reset_clients = {"pi": "pi", "opencode": "opencode", "codex": "codex-cli"}
    for client in ("pi", "opencode", "codex"):
        reset_result = run(
            [
                str(python),
                str(harness_root / "scripts" / "reset-client-harness-state.py"),
                "--client",
                reset_clients[client],
                "--reset-home-volume",
                "--evidence-dir",
                "docker/client-harness/evidence/use-case-13/prior",
            ],
            cwd=repo_root,
            timeout=120,
            env=runtime_env,
            ledger=ledger,
        )
        reset_json = parse_json_stdout(reset_result)
        command_statuses[f"{client}_reset"] = status(reset_result)

        if args.skip_runtime:
            smoke_result = {
                "returncode": 0,
                "timeout": False,
                "required": False,
                "stdout": "runtime skipped by --skip-runtime",
                "stderr": "",
            }
        elif client == "pi":
            smoke_result = run(
                [str(harness_root / "scripts" / "smoke-pi-contextforge-dev.sh")],
                cwd=harness_root,
                timeout=args.timeout,
                env=runtime_env,
                ledger=ledger,
            )
        elif client == "opencode":
            smoke_env = dict(runtime_env)
            smoke_env["OPENCODE_REQUIRE_SAFE_CALL"] = "0"
            smoke_result = run(
                [str(harness_root / "scripts" / "smoke-opencode-contextforge-dev.sh")],
                cwd=harness_root,
                timeout=args.timeout,
                env=smoke_env,
                ledger=ledger,
            )
        else:
            smoke_result = run(
                [str(harness_root / "scripts" / "smoke-codex-contextforge-dev.sh")],
                cwd=harness_root,
                timeout=args.timeout,
                env=runtime_env,
                ledger=ledger,
            )
        command_statuses[f"{client}_smoke"] = status(smoke_result, required=not args.skip_runtime)
        evidence_names = {
            "pi": "pi-contextforge-dev-smoke.txt",
            "opencode": "opencode-contextforge-dev-smoke.txt",
            "codex": "codex-contextforge-dev-smoke.txt",
        }
        claim_boundaries = {
            "pi": "Pi shim readback against dev gateway",
            "opencode": "OpenCode dev gateway MCP add/list; safe call not claimed unless OPENCODE_SAFE_CALL_COMMAND is supplied",
            "codex": "Codex authenticated Docker config/list readback against dev gateway; safe call and dialogue not claimed",
        }
        evidence_name = evidence_names[client]
        clients[client] = {
            "reset_json": reset_json,
            "reset_client": reset_clients[client],
            "smoke_status": status(smoke_result, required=not args.skip_runtime),
            "evidence_artifact": str(harness_root / "evidence" / evidence_name),
            "evidence_artifact_status": artifact_status(harness_root / "evidence" / evidence_name),
            "host_global_client_mutated": False,
            "client_container_surface": f"{client} Docker client harness",
            "runtime_skipped": bool(args.skip_runtime),
            "claim_boundary": claim_boundaries[client],
        }

    selected_dialogue = [
        {
            "use_case": "use-case-12",
            "client": "pi",
            "package": latest_package(repo_root, "use-case-12", "pi"),
            "semantic_evaluator_required": True,
            "accepted_elsewhere": True,
        },
        {
            "use_case": "use-case-12",
            "client": "opencode",
            "package": latest_package(repo_root, "use-case-12", "opencode"),
            "semantic_evaluator_required": True,
            "accepted_elsewhere": True,
        },
        {
            "use_case": "use-case-12",
            "client": "codex",
            "package": latest_package(repo_root, "use-case-12", "codex"),
            "semantic_evaluator_required": True,
            "accepted_elsewhere": True,
        },
    ]

    metadata = {
        "use_case": "use-case-13",
        "timestamp": timestamp,
        "semantic_acceptance": "not_a_dialogue_semantic_acceptance",
        "deterministic_checks_are_structural_only": True,
        "runtime_skipped": bool(args.skip_runtime),
        "python_surface": {
            "executable": str(python),
            "current_worktree_test_venv": True,
            "sibling_venv_substitution": False,
        },
        "dev_surface": {
            "host_base_url": "http://127.0.0.1:4445",
            "container_base_url": "http://host.docker.internal:4445",
            "gateway_compose": str(contextforge_root / "compose.yml"),
            "legacy_live_contextforge_mutated": False,
            "direct_database_writes": False,
        },
        "clients": clients,
        "command_statuses": command_statuses,
        "selected_use_case_dialogue_evidence": selected_dialogue,
        "non_actions": [
            "did not mutate host-global Pi state",
            "did not mutate host-global OpenCode state",
            "did not mutate live/legacy ContextForge",
            "did not direct-write ContextForge database state",
            "did not claim OpenCode safe-call proof from list-only evidence",
        ],
    }

    metadata_path = output_root / f"use-case-13-metadata-{timestamp}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verifier_result = run(
        [
            str(python),
            str(harness_root / "scripts" / "verify-use-case-13-controlled-dev-evidence.py"),
            "--metadata",
            str(metadata_path),
        ],
        cwd=repo_root,
        timeout=120,
        env=runtime_env,
        ledger=ledger,
    )
    verifier_json = parse_json_stdout(verifier_result)
    verifier_path = output_root / f"use-case-13-verifier-{timestamp}.json"
    verifier_path.write_text(json.dumps(verifier_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    package_path = output_root / f"use-case-13-evaluation-package-{timestamp}.md"
    package_path.write_text(render_package(metadata, verifier_json, ledger), encoding="utf-8")

    summary = {
        "ok": bool(isinstance(verifier_json, dict) and verifier_json.get("ok")),
        "ok_scope": "controlled dev evidence package assembled; not semantic dialogue acceptance",
        "metadata": str(metadata_path),
        "verifier": str(verifier_path),
        "evaluation_package_markdown": str(package_path),
        "runtime_skipped": bool(args.skip_runtime),
        "clients": {
            client: {
                "evidence_artifact": record["evidence_artifact"],
                "smoke_status": record["smoke_status"],
            }
            for client, record in clients.items()
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
