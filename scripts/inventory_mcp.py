#!/usr/bin/env python3
"""Read-only MCP/client service inventory for the local ContextForge project."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET_RE = re.compile(r"(token|secret|password|key|credential|auth)", re.IGNORECASE)

CONFIG_CANDIDATES = [
    ("codex-terminal", "~/.codex/config.toml"),
    ("codex-desktop", "~/.local/share/codex-desktop-linux/config.toml"),
    ("claude-desktop", "~/.config/Claude/claude_desktop_config.json"),
    ("claude-code", "~/.claude.json"),
    ("claude-code", "~/.claude/settings.json"),
    ("gemini-cli", "~/.gemini/settings.json"),
    ("gemini-cli", "~/.gemini/antigravity/mcp_config.json"),
    ("opencode", "~/.config/opencode/opencode.json"),
    ("anythingllm", "~/.config/anythingllm-desktop/storage/plugins/anythingllm_mcp_servers.json"),
]

WORKSPACE_ROOT_PATTERNS = [
    "~/workspace",
    "~/workspace-*",
    "~/workspace_*",
]
PRUNE_DIRS = {".git", ".venv", "node_modules", "dist", "build", "vendor", "__pycache__", "upstream"}
WORKSPACE_CONFIG_NAMES = {
    ".claude.json",
    "opencode.json",
    "mcp.json",
    ".mcp.json",
    "mcp_config.json",
    "settings.json",
    "config.toml",
}
WORKSPACE_CONFIG_DIRS = {".pi", ".pi-user", ".claude", ".gemini", ".codex", ".opencode"}
SOURCE_HINT_RE = re.compile(
    r"FastMCP|McpServer|@modelcontextprotocol|mcpgateway|openapi|OpenAPI|REST|rest api|"
    r"pi-web-access|pi-claude-bridge",
    re.IGNORECASE,
)


def redact(value: Any, key: str = "") -> Any:
    if SECRET_RE.search(key):
        if value in (None, "", [], {}):
            return value
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    return value


def load_config(path: Path) -> Any:
    if path.suffix == ".toml":
        return tomllib.loads(path.read_text(encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def find_mcp_maps(obj: Any, trail: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], dict[str, Any]]]:
    found: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_text = str(key)
            if key_text in {"mcpServers", "mcp_servers", "mcpServersConfig"} and isinstance(value, dict):
                found.append((trail + (key_text,), value))
            elif key_text in {"mcp", "context_servers", "contextServers"} and isinstance(value, dict):
                if all(isinstance(item, dict) for item in value.values()):
                    found.append((trail + (key_text,), value))
                found.extend(find_mcp_maps(value, trail + (key_text,)))
            else:
                found.extend(find_mcp_maps(value, trail + (key_text,)))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            found.extend(find_mcp_maps(value, trail + (str(index),)))
    return found


def find_pi_packages(obj: Any, trail: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], list[str]]]:
    found: list[tuple[tuple[str, ...], list[str]]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "packages" and isinstance(value, list):
                packages = [item for item in value if isinstance(item, str) and item.startswith("npm:pi-")]
                if packages:
                    found.append((trail + (key,), packages))
            else:
                found.extend(find_pi_packages(value, trail + (str(key),)))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            found.extend(find_pi_packages(value, trail + (str(index),)))
    return found


def classify_transport(config: dict[str, Any]) -> str:
    transport = str(config.get("transport") or config.get("type") or "").lower()
    url = str(config.get("url") or config.get("uri") or config.get("endpoint") or "")
    if "sse" in transport or url.rstrip("/").endswith("/sse") or "/sse" in url:
        return "sse"
    if "streamable" in transport or "http" in transport or url.startswith(("http://", "https://")):
        return "streamable_http"
    if config.get("command") or config.get("args"):
        return "stdio"
    return "unknown"


def classify_client_from_workspace_path(path: Path) -> str:
    parts = path.parts
    if ".pi" in parts or ".pi-user" in parts:
        return "pi-coding-assistant"
    if ".claude" in parts or path.name == ".claude.json":
        return "claude-code-project"
    if ".gemini" in parts:
        return "gemini-cli-project"
    if ".codex" in parts:
        return "codex-project"
    if ".opencode" in parts or path.name == "opencode.json":
        return "opencode-project"
    return "workspace-project"


def workspace_roots() -> list[Path]:
    roots: list[Path] = []
    for pattern in WORKSPACE_ROOT_PATTERNS:
        roots.extend(Path.home().glob(pattern.replace("~/", "")))
    return sorted({path.resolve() for path in roots if path.exists()})


def workspace_config_paths() -> list[Path]:
    roots = workspace_roots()

    paths: list[Path] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in PRUNE_DIRS]
            path = Path(dirpath)
            parent_names = set(path.parts)
            if parent_names & WORKSPACE_CONFIG_DIRS:
                for filename in filenames:
                    if filename in WORKSPACE_CONFIG_NAMES:
                        paths.append(path / filename)
            else:
                for filename in filenames:
                    if filename in {
                        ".claude.json",
                        "opencode.json",
                        "mcp.json",
                        ".mcp.json",
                        "mcp_config.json",
                    }:
                        paths.append(path / filename)
    return sorted(set(paths))


def workspace_source_hints() -> list[dict[str, Any]]:
    try:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                "--hidden",
                "--glob",
                "!**/.git/**",
                "--glob",
                "!**/node_modules/**",
                "--glob",
                "!**/.venv/**",
                "--glob",
                "!**/dist/**",
                "--glob",
                "!**/build/**",
                "--glob",
                "!**/upstream/**",
                SOURCE_HINT_RE.pattern,
                *[str(path) for path in workspace_roots()],
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    hints: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines()[:500]:
        path, sep, rest = line.partition(":")
        if not sep:
            continue
        lineno, sep, text = rest.partition(":")
        if not sep:
            continue
        hints.append(
            {
                "source": path,
                "line": int(lineno) if lineno.isdigit() else None,
                "text": redact(text.strip())[:240],
            }
        )
    return hints


def inventory_entry(client: str, source: Path, name: str, config: dict[str, Any], trail: tuple[str, ...]) -> dict[str, Any]:
    sanitized = redact(config)
    return {
        "name": name,
        "client": client,
        "source": str(source),
        "config_path": ".".join(trail),
        "enabled": not bool(config.get("disabled") or config.get("enabled") is False),
        "transport": classify_transport(config),
        "has_command": bool(config.get("command")),
        "has_url": bool(config.get("url") or config.get("uri") or config.get("endpoint")),
        "config": sanitized,
    }


def pi_package_entry(client: str, source: Path, package: str, trail: tuple[str, ...]) -> dict[str, Any]:
    return {
        "name": package.removeprefix("npm:"),
        "client": client,
        "source": str(source),
        "config_path": ".".join(trail),
        "enabled": True,
        "transport": "assistant_package",
        "has_command": False,
        "has_url": False,
        "config": {
            "package": package,
        },
    }


def add_entries_from_config(entries: list[dict[str, Any]], source: dict[str, Any], client: str, path: Path) -> None:
    if not path.exists():
        return
    try:
        data = load_config(path)
    except Exception as exc:  # noqa: BLE001 - inventory should report and continue.
        source["error"] = str(exc)
        return
    for trail, mcp_map in find_mcp_maps(data):
        for name, config in mcp_map.items():
            if isinstance(config, dict):
                entries.append(inventory_entry(client, path, str(name), config, trail))
    for trail, packages in find_pi_packages(data):
        for package in packages:
            entries.append(pi_package_entry(client, path, package, trail))


def discover() -> dict[str, Any]:
    entries: list[dict[str, Any]] = [
        {
            "name": "mentality",
            "client": "context-portal",
            "source": str(REPO_ROOT / "scripts/governance_mcp.py"),
            "config_path": "static.repo_local",
            "enabled": True,
            "transport": "stdio",
            "has_command": True,
            "has_url": False,
            "config": {
                "command": str(REPO_ROOT / ".venv/bin/python"),
                "args": [str(REPO_ROOT / "scripts/governance_mcp.py")],
            },
        }
    ]
    sources: list[dict[str, Any]] = []
    for client, raw_path in CONFIG_CANDIDATES:
        path = Path(os.path.expanduser(raw_path))
        source = {"client": client, "path": str(path), "exists": path.exists(), "error": None}
        sources.append(source)
        add_entries_from_config(entries, source, client, path)

    for path in workspace_config_paths():
        client = classify_client_from_workspace_path(path)
        source = {"client": client, "path": str(path), "exists": True, "error": None}
        sources.append(source)
        add_entries_from_config(entries, source, client, path)
    transport_counts: dict[str, int] = {}
    client_counts: dict[str, int] = {}
    for entry in entries:
        transport_counts[entry["transport"]] = transport_counts.get(entry["transport"], 0) + 1
        client_counts[entry["client"]] = client_counts.get(entry["client"], 0) + 1
    return {
        "repository": str(REPO_ROOT),
        "sources": sources,
        "summary": {
            "entries": len(entries),
            "enabled": sum(1 for entry in entries if entry["enabled"]),
            "by_transport": dict(sorted(transport_counts.items())),
            "by_client": dict(sorted(client_counts.items())),
        },
        "entries": entries,
        "source_hints": workspace_source_hints(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "inventory/contextforge-services.local.json"),
        help="Ignored local JSON inventory output path.",
    )
    args = parser.parse_args()
    result = discover()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
