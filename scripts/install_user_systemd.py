#!/usr/bin/env python3
"""Install user-level systemd units for the canonical ContextForge stack."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
USER_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
NODE_BIN = Path.home() / ".nvm" / "versions" / "node" / "v24.12.0" / "bin"
SYSTEMD_PATH = f"{NODE_BIN}:{Path.home() / '.local/bin'}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
STACK_TARGET = "contextforge.target"
GATEWAY_ENV = REPO_ROOT / "config" / "contextforge.env"
PLAN_SCHEMA_URI = "contextforge://diagnostics/user-systemd-install-plan/v1"


def unit_header(description: str, *, after: str = "network.target", wants: str | None = None) -> str:
    wants_line = f"Wants={wants}\n" if wants else ""
    return f"""[Unit]
Description={description}
After={after}
{wants_line}

"""


def service_unit(
    description: str,
    exec_start: str,
    *,
    env_files: list[Path] | None = None,
    after: str = "network.target",
    wants: str | None = None,
) -> str:
    env_file_lines = ""
    for path in env_files or []:
        env_file_lines += f"EnvironmentFile=-{path}\n"
    return (
        unit_header(description, after=after, wants=wants)
        + f"""[Service]
Type=simple
WorkingDirectory={REPO_ROOT}
Environment=PATH={SYSTEMD_PATH}
{env_file_lines}ExecStart={exec_start}
Restart=on-failure
RestartSec=3

[Install]
WantedBy={STACK_TARGET}
"""
    )


def gateway_unit() -> str:
    return (
        unit_header("ContextForge Gateway")
        + f"""[Service]
Type=simple
WorkingDirectory={REPO_ROOT}
Environment=PATH={SYSTEMD_PATH}
EnvironmentFile={GATEWAY_ENV}
ExecStart={REPO_ROOT / '.venv' / 'bin' / 'mcpgateway'} --env-file {GATEWAY_ENV} --host 127.0.0.1 --port 4444
Restart=on-failure
RestartSec=3

[Install]
WantedBy={STACK_TARGET}
"""
    )


def target_unit() -> str:
    return """[Unit]
Description=ContextForge local stack
Wants=contextforge-gateway.service contextforge-mentality.service contextforge-ssh-tmux.service contextforge-context7.service contextforge-playwright.service contextforge-exa-search.service contextforge-github.service contextforge-web-search.service contextforge-serena-cf-controlplane-d46fe58a2a20.service
After=network.target

[Install]
WantedBy=default.target
"""


def units() -> dict[str, str]:
    return {
        "contextforge.target": target_unit(),
        "contextforge-gateway.service": gateway_unit(),
        "contextforge-mentality.service": service_unit(
            "ContextForge mentality governance MCP bridge",
            f"{REPO_ROOT / 'server-instances' / 'mentality' / 'run-bridge.sh'}",
        ),
        "contextforge-ssh-tmux.service": service_unit(
            "ContextForge ssh-tmux MCP bridge",
            f"{REPO_ROOT / 'server-instances' / 'ssh-tmux' / 'run-bridge.sh'}",
        ),
        "contextforge-context7.service": service_unit(
            "ContextForge Context7 MCP bridge",
            f"{REPO_ROOT / 'server-instances' / 'context7' / 'run-server.sh'}",
            env_files=[REPO_ROOT / "server-instances" / "context7" / ".env"],
        ),
        "contextforge-playwright.service": service_unit(
            "ContextForge Playwright MCP server",
            f"{REPO_ROOT / 'server-instances' / 'playwright' / 'run-server.sh'}",
        ),
        "contextforge-exa-search.service": service_unit(
            "ContextForge Exa Search Gemini MCP bridge",
            f"{REPO_ROOT / 'server-instances' / 'exa-search' / 'run-bridge.sh'}",
            env_files=[REPO_ROOT / "server-instances" / "exa-search" / ".env"],
        ),
        "contextforge-github.service": service_unit(
            "ContextForge GitHub MCP bridge",
            f"{REPO_ROOT / 'server-instances' / 'github' / 'run-bridge.sh'}",
        ),
        "contextforge-web-search.service": service_unit(
            "ContextForge web_search MCP bridge",
            f"{REPO_ROOT / 'server-instances' / 'web-search' / 'run-bridge.sh'}",
            env_files=[REPO_ROOT / "server-instances" / "web-search" / ".env"],
        ),
        "contextforge-serena-cf-controlplane-d46fe58a2a20.service": service_unit(
            "ContextForge Serena MCP server for cf-controlplane",
            f"{REPO_ROOT / 'server-instances' / 'serena-cf-controlplane-d46fe58a2a20' / 'run-server.sh'}",
            after="network.target contextforge-gateway.service",
            wants="contextforge-gateway.service",
        ),
    }


def install_units() -> list[Path]:
    USER_UNIT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in units().items():
        path = USER_UNIT_DIR / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_current_unit(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _absolute_paths(text: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"(/[^\s\"']+)", text):
        raw = match.group(1).rstrip("\\")
        candidates = raw.split(":") if ":" in raw else [raw]
        for candidate in candidates:
            if candidate.startswith("/") and candidate not in seen:
                seen.add(candidate)
                paths.append(candidate)
    return paths


def _workspace_roots_outside_repo(text: str) -> list[str]:
    roots: set[str] = set()
    workspace_root = REPO_ROOT.parent
    for path_text in _absolute_paths(text):
        try:
            path = Path(path_text)
            relative = path.relative_to(workspace_root)
        except ValueError:
            continue
        if not relative.parts:
            continue
        root = workspace_root / relative.parts[0]
        if root != REPO_ROOT:
            roots.add(str(root))
    return sorted(roots)


def _environment_file_refs(text: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("EnvironmentFile="):
            continue
        value = stripped.split("=", 1)[1]
        optional = value.startswith("-")
        path_text = value[1:] if optional else value
        path = Path(path_text)
        refs.append(
            {
                "path": path_text,
                "optional": optional,
                "exists": path.exists(),
                "is_file": path.is_file(),
            }
        )
    return refs


def build_install_plan(*, user_unit_dir: Path = USER_UNIT_DIR) -> dict[str, Any]:
    desired_units = units()
    unit_plans = []
    for name, desired in desired_units.items():
        path = user_unit_dir / name
        current = _read_current_unit(path)
        current_digest = _sha256_text(current) if current is not None else None
        desired_digest = _sha256_text(desired)
        current_matches_desired = current_digest == desired_digest
        unit_plans.append(
            {
                "unit": name,
                "path": str(path),
                "installed": current is not None,
                "current_matches_desired": current_matches_desired,
                "action": "unchanged" if current_matches_desired else "write_or_replace",
                "current_sha256": current_digest,
                "desired_sha256": desired_digest,
                "current_workspace_roots_outside_repo": _workspace_roots_outside_repo(current or ""),
                "desired_workspace_roots_outside_repo": _workspace_roots_outside_repo(desired),
                "current_environment_files": _environment_file_refs(current or ""),
                "desired_environment_files": _environment_file_refs(desired),
            }
        )
    return {
        "schema_uri": PLAN_SCHEMA_URI,
        "repo_root": str(REPO_ROOT),
        "user_unit_dir": str(user_unit_dir),
        "mutation_performed": False,
        "summary": {
            "desired_unit_count": len(desired_units),
            "installed_unit_count": sum(1 for unit in unit_plans if unit["installed"]),
            "matching_unit_count": sum(1 for unit in unit_plans if unit["current_matches_desired"]),
            "write_or_replace_count": sum(1 for unit in unit_plans if unit["action"] == "write_or_replace"),
            "units_with_current_external_workspace_roots": [
                unit["unit"] for unit in unit_plans if unit["current_workspace_roots_outside_repo"]
            ],
            "units_with_missing_required_desired_env_files": [
                unit["unit"]
                for unit in unit_plans
                if any(
                    not ref["optional"] and not ref["exists"]
                    for ref in unit["desired_environment_files"]
                )
            ],
        },
        "units": unit_plans,
        "non_actions": [
            "read-only plan; no unit files written",
            "read-only plan; no systemctl command executed",
            "read-only plan; no services stopped, started, restarted, or reloaded",
            "read-only plan; no environment file contents read",
        ],
    }


def run_systemctl(args: list[str]) -> None:
    subprocess.run(["systemctl", "--user", *args], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-enable", action="store_true", help="Write units but do not enable them")
    parser.add_argument("--start", action="store_true", help=f"Start {STACK_TARGET} after installation")
    parser.add_argument(
        "--plan-json",
        action="store_true",
        help="Print a read-only JSON comparison of desired and current user units.",
    )
    args = parser.parse_args()

    if args.plan_json:
        print(json.dumps(build_install_plan(), indent=2, sort_keys=True))
        return 0

    written = install_units()
    for path in written:
        print(path)

    run_systemctl(["daemon-reload"])
    if not args.no_enable:
        run_systemctl(["enable", STACK_TARGET])
        service_names = [name for name in units() if name.endswith(".service")]
        run_systemctl(["enable", *service_names])
    if args.start:
        run_systemctl(["start", STACK_TARGET])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
