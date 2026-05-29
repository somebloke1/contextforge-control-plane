#!/usr/bin/env python3
"""Install user-level systemd units for the canonical ContextForge stack."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]
USER_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
NODE_BIN = Path.home() / ".nvm" / "versions" / "node" / "v24.12.0" / "bin"
SYSTEMD_PATH = f"{NODE_BIN}:{Path.home() / '.local/bin'}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
STACK_TARGET = "contextforge.target"
GATEWAY_ENV = REPO_ROOT / "config" / "contextforge.env"


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
Wants=contextforge-gateway.service contextforge-mentality.service contextforge-ssh-tmux.service contextforge-context7.service contextforge-playwright.service contextforge-exa-search.service contextforge-github.service contextforge-web-search.service contextforge-serena-context-portal.service
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
        "contextforge-serena-context-portal.service": service_unit(
            "ContextForge Serena MCP server for context-portal",
            f"{REPO_ROOT / 'server-instances' / 'serena-context-portal' / 'run-server.sh'}",
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


def run_systemctl(args: list[str]) -> None:
    subprocess.run(["systemctl", "--user", *args], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-enable", action="store_true", help="Write units but do not enable them")
    parser.add_argument("--start", action="store_true", help=f"Start {STACK_TARGET} after installation")
    args = parser.parse_args()

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
