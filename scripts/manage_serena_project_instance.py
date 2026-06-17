#!/usr/bin/env python3
"""Provision one ContextForge-owned Serena backend for a project."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import select
import shutil
import socket
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import contextforge_mcp_wrapper as gateway

from project_init_common import (
    ENV_PROJECT_INIT_STATUS,
    ENV_SERENA_DECISION,
    ENV_SERENA_INSTANCE_SLUG,
    ENV_SERENA_PROVISION_STATUS,
    ENV_SERENA_SERVER_NAME,
    PROJECT_INIT_PROMPT_NAME,
    PROJECT_INIT_RESOURCE_URI,
    REPO_ROOT,
    RUN_ROOT,
    SERENA_GUIDANCE_PROMPT_NAME,
    SERENA_GUIDANCE_RESOURCE_URI,
    project_identity,
    validate_project_root,
    write_project_env,
)


PORT_RANGE = range(9110, 9200)
OPERATOR_RESERVED_PORTS = frozenset({9108})
EXCLUDED_ORIGINAL_TOOL_NAMES = {"activate_project"}
OWNER = "admin@contextforge.dev"
VISIBILITY = "public"
SYSTEMD_USER_DIR = Path.home() / ".config/systemd/user"
WRAPPER_PATH = REPO_ROOT / "scripts/contextforge_mcp_wrapper.py"
PYTHON_PATH = REPO_ROOT / ".venv/bin/python"
LOCK_PATH = RUN_ROOT / "serena-instance-manager.local.lock"
SYSTEMD_PATH = "/home/dgk/.nvm/versions/node/v24.12.0/bin:/home/dgk/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SUPPORTED_LANGUAGES = {
    "al",
    "angular",
    "ansible",
    "bash",
    "clojure",
    "cpp",
    "cpp_ccls",
    "crystal",
    "csharp",
    "csharp_omnisharp",
    "dart",
    "elixir",
    "elm",
    "erlang",
    "fortran",
    "fsharp",
    "go",
    "groovy",
    "haskell",
    "haxe",
    "hlsl",
    "html",
    "java",
    "json",
    "julia",
    "kotlin",
    "lean4",
    "lua",
    "luau",
    "markdown",
    "matlab",
    "msl",
    "nix",
    "ocaml",
    "pascal",
    "perl",
    "php",
    "php_phpactor",
    "powershell",
    "python",
    "python_jedi",
    "python_ty",
    "r",
    "rego",
    "ruby",
    "ruby_solargraph",
    "rust",
    "scala",
    "scss",
    "solidity",
    "svelte",
    "swift",
    "systemverilog",
    "terraform",
    "toml",
    "typescript",
    "typescript_vts",
    "vue",
    "yaml",
    "zig",
}
RECOMMENDED_LANGUAGE_EXAMPLES = (
    "python",
    "typescript",
    "javascript",
    "rust",
    "go",
    "bash",
    "java",
    "csharp",
    "cpp",
)
LANGUAGE_PROBE_FILES = {
    "python": ("contextforge_serena_probe.py", "def contextforge_serena_probe():\n    return 42\n"),
    "python_jedi": ("contextforge_serena_probe.py", "def contextforge_serena_probe():\n    return 42\n"),
    "python_ty": ("contextforge_serena_probe.py", "def contextforge_serena_probe():\n    return 42\n"),
    "typescript": ("contextforge_serena_probe.ts", "export function contextforgeSerenaProbe(): number {\n  return 42;\n}\n"),
    "typescript_vts": ("contextforge_serena_probe.ts", "export function contextforgeSerenaProbe(): number {\n  return 42;\n}\n"),
    "javascript": ("contextforge_serena_probe.ts", "export function contextforgeSerenaProbe(): number {\n  return 42;\n}\n"),
    "go": ("contextforge_serena_probe.go", "package main\n\nfunc contextforgeSerenaProbe() int {\n\treturn 42\n}\n"),
    "rust": ("contextforge_serena_probe.rs", "fn contextforge_serena_probe() -> i32 {\n    42\n}\n"),
    "java": ("ContextforgeSerenaProbe.java", "class ContextforgeSerenaProbe {\n    int value() { return 42; }\n}\n"),
    "ruby": ("contextforge_serena_probe.rb", "def contextforge_serena_probe\n  42\nend\n"),
    "php": ("contextforge_serena_probe.php", "<?php\nfunction contextforge_serena_probe() {\n    return 42;\n}\n"),
    "bash": ("contextforge_serena_probe.sh", "contextforge_serena_probe() {\n  echo 42\n}\n"),
}
LANGUAGE_EXTENSIONS = {
    "python": (".py",),
    "python_jedi": (".py",),
    "python_ty": (".py",),
    "typescript": (".ts", ".tsx", ".js", ".jsx"),
    "typescript_vts": (".ts", ".tsx", ".js", ".jsx"),
    "go": (".go",),
    "rust": (".rs",),
    "java": (".java",),
    "ruby": (".rb",),
    "php": (".php",),
    "bash": (".sh", ".bash"),
    "yaml": (".yaml", ".yml"),
    "json": (".json",),
    "toml": (".toml",),
    "markdown": (".md",),
    "html": (".html", ".htm"),
    "scss": (".scss", ".css", ".sass"),
}
LANGUAGE_MARKERS = (
    ("pyproject.toml", "python"),
    ("requirements.txt", "python"),
    ("setup.py", "python"),
    ("package.json", "typescript"),
    ("tsconfig.json", "typescript"),
    ("go.mod", "go"),
    ("Cargo.toml", "rust"),
)
LANGUAGE_INFERENCE_ORDER = (
    "python",
    "typescript",
    "go",
    "rust",
    "java",
    "ruby",
    "php",
    "bash",
    "html",
    "scss",
    "yaml",
    "json",
    "toml",
    "markdown",
)
IGNORED_PROBE_DIRS = {".codex", ".git", ".serena", "__pycache__", "node_modules", ".venv", "run"}
LANGUAGE_ALIASES = {"javascript": "typescript"}
LSP_GAP_NONE = "none"
LSP_GAP_OPTIONAL = "optional_capability_gap"
LSP_GAP_RECOMMENDED = "recommended_improvement"
LSP_GAP_BASELINE = "baseline_blocking"
LSP_UNSUPPORTED_ERROR_CODE = -32601
READ_ONLY_BASELINE_LSP_TOOL_SUFFIXES = (
    "get-diagnostics-for-file",
    "get-symbols-overview",
    "find-declaration",
    "find-referencing-symbols",
)
READ_ONLY_OPTIONAL_LSP_TOOL_SUFFIXES = ("find-implementations",)
EDIT_LSP_TOOL_SUFFIXES = (
    "insert-after-symbol",
    "insert-before-symbol",
    "rename-symbol",
    "replace-symbol-body",
    "safe-delete-symbol",
)
LSP_TOOLS_DIRNAME = "lsp-tools"
LSP_SCAFFOLD_DIRS = (
    LSP_TOOLS_DIRNAME,
    f"{LSP_TOOLS_DIRNAME}/bin",
    f"{LSP_TOOLS_DIRNAME}/cache",
    f"{LSP_TOOLS_DIRNAME}/cache/xdg",
    f"{LSP_TOOLS_DIRNAME}/logs",
    f"{LSP_TOOLS_DIRNAME}/solidlsp",
)
LSP_BACKEND_CATALOG: dict[str, list[dict[str, Any]]] = {
    "python": [
        {
            "backend_id": "python",
            "label": "Pyright for Python",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "pyright",
            "caveats": ["find implementations is optional for Python backends"],
        },
        {
            "backend_id": "python_jedi",
            "label": "Jedi for Python",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "jedi-language-server",
            "caveats": ["different behavior from the default Pyright backend"],
        },
        {
            "backend_id": "python_ty",
            "label": "Ty for Python",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "ty",
            "caveats": ["experimental Serena backend"],
        },
    ],
    "typescript": [
        {
            "backend_id": "typescript",
            "label": "TypeScript language server",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "typescript-language-server",
            "caveats": ["JavaScript projects should use this Serena language id"],
        },
        {
            "backend_id": "typescript_vts",
            "label": "VTS TypeScript backend",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "vtsls",
            "caveats": ["alternative TypeScript behavior"],
        },
    ],
    "rust": [
        {
            "backend_id": "rust",
            "label": "Rust Analyzer",
            "strategy_class": "host_required",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "rust-analyzer",
            "host_tools": ["cargo", "rustc", "rust-analyzer"],
            "caveats": ["do not mutate rustup automatically"],
        }
    ],
    "go": [
        {
            "backend_id": "go",
            "label": "gopls for Go",
            "strategy_class": "path_tool",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "gopls",
            "host_tools": ["go", "gopls"],
            "caveats": ["project modules remain project-local"],
        }
    ],
    "bash": [
        {
            "backend_id": "bash",
            "label": "Bash language support",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "bash-language-server",
            "caveats": ["richer shell support is optional"],
        }
    ],
    "java": [
        {
            "backend_id": "java",
            "label": "Java language server",
            "strategy_class": "host_required",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "jdtls",
            "caveats": ["heavy backend; require explicit approval later"],
        }
    ],
    "csharp": [
        {
            "backend_id": "csharp",
            "label": "C# language server",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "csharp-language-server",
            "caveats": [],
        },
        {
            "backend_id": "csharp_omnisharp",
            "label": "OmniSharp for C#",
            "strategy_class": "host_required",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "omnisharp",
            "caveats": ["explicit alternative"],
        },
    ],
    "cpp": [
        {
            "backend_id": "cpp",
            "label": "Clangd for C and C++",
            "strategy_class": "path_tool",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "clangd",
            "caveats": [],
        },
        {
            "backend_id": "cpp_ccls",
            "label": "ccls for C and C++",
            "strategy_class": "path_tool",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "ccls",
            "caveats": ["explicit manual alternative"],
        },
    ],
    "ruby": [
        {
            "backend_id": "ruby",
            "label": "Ruby language server",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "ruby-lsp",
            "caveats": [],
        },
        {
            "backend_id": "ruby_solargraph",
            "label": "Solargraph for Ruby",
            "strategy_class": "path_tool",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "solargraph",
            "caveats": ["no global gem install"],
        },
    ],
    "php": [
        {
            "backend_id": "php",
            "label": "PHP language server",
            "strategy_class": "solidlsp_managed",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "intelephense",
            "caveats": [],
        },
        {
            "backend_id": "php_phpactor",
            "label": "Phpactor for PHP",
            "strategy_class": "path_tool",
            "install_implemented": False,
            "recommended_scope": "instance",
            "tool_identity": "phpactor",
            "caveats": ["explicit alternative"],
        },
    ],
}
RUST_ANALYZER_MISSING_COMPONENT_TEXT = "Unknown binary 'rust-analyzer' in official toolchain"


def run(command: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=capture,
        check=check,
    )


def normalize_language_id(language: str | None) -> str | None:
    if language is None:
        return None
    normalized = language.strip().lower()
    return LANGUAGE_ALIASES.get(normalized, normalized)


def supported_languages() -> set[str]:
    try:
        from solidlsp.ls_config import Language  # type: ignore

        values = {
            str(getattr(item, "value", item)).lower()
            for item in Language  # type: ignore[union-attr]
            if str(getattr(item, "value", item)).strip()
        }
        return values | set(LANGUAGE_ALIASES)
    except Exception:
        return set(SUPPORTED_LANGUAGES) | set(LANGUAGE_ALIASES)


def install_command_execution_enabled() -> bool:
    return False


def classify_tool_probe(tool: str, returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
    combined = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
    if tool == "rust-analyzer" and RUST_ANALYZER_MISSING_COMPONENT_TEXT in combined:
        return {
            "usable": False,
            "classification": "rustup_proxy_missing_component",
            "detail": combined,
            "standard_provider": "contextforge_standard_rust_analyzer",
            "recommended_resolution": "Use a curated Rust Analyzer provider: either approve host rustup component installation or place an approved rust-analyzer binary in the Serena instance lsp-tools/bin directory.",
        }
    if returncode == 0:
        return {"usable": True, "classification": "ok", "detail": combined}
    return {"usable": False, "classification": "probe_failed", "detail": combined}


def host_tool_status(tool: str) -> dict[str, Any]:
    path = shutil.which(tool)
    if path is None:
        return {
            "visible": False,
            "usable": False,
            "path": None,
            "classification": "not_found",
        }
    try:
        proc = subprocess.run(
            [path, "--version"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except Exception as exc:
        return {
            "visible": True,
            "usable": False,
            "path": path,
            "classification": "probe_exception",
            "detail": str(exc),
        }
    classified = classify_tool_probe(tool, proc.returncode, proc.stdout, proc.stderr)
    return {
        "visible": True,
        "path": path,
        **classified,
    }


def lsp_standard_provider(language: str | None, options: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized = normalize_language_id(language)
    if normalized != "rust":
        return None
    rust_analyzer_status = {}
    for option in options:
        statuses = option.get("host_tool_status")
        if isinstance(statuses, dict) and isinstance(statuses.get("rust-analyzer"), dict):
            rust_analyzer_status = statuses["rust-analyzer"]
            break
    status = "available" if rust_analyzer_status.get("usable") else "blocked"
    choices = [
        {
            "label": "Keep Current Backend",
            "description": "Leave Serena configured for Rust and report the current LSP limitation.",
            "implemented": True,
        },
        {
            "label": "Configure Standard Rust Analyzer",
            "description": "Use ContextForge's curated Rust Analyzer provider path, preferring instance-local lsp-tools/bin and requiring explicit approval before any install.",
            "implemented": False,
        },
        {
            "label": "Defer Limitation",
            "description": "Record the Rust LSP baseline blocker and continue with non-LSP Serena tools only.",
            "implemented": True,
        },
    ]
    return {
        "provider_id": "contextforge_standard_rust_analyzer",
        "label": "Standard Rust Analyzer provider",
        "language": "rust",
        "status": status,
        "problem": rust_analyzer_status.get("classification"),
        "detail": rust_analyzer_status.get("detail"),
        "recommended_scope": "instance",
        "install_implemented": False,
        "install_command_execution_enabled": install_command_execution_enabled(),
        "choices": choices,
    }


def automatic_lsp_probe_tool_suffixes(*, include_optional: bool = False) -> tuple[str, ...]:
    suffixes = READ_ONLY_BASELINE_LSP_TOOL_SUFFIXES
    if include_optional:
        suffixes = suffixes + READ_ONLY_OPTIONAL_LSP_TOOL_SUFFIXES
    edits = set(EDIT_LSP_TOOL_SUFFIXES)
    if any(suffix in edits for suffix in suffixes):
        raise RuntimeError("automatic LSP probes must not include edit tools")
    return suffixes


def lsp_backend_options(language: str | None) -> list[dict[str, Any]]:
    normalized = normalize_language_id(language)
    if not normalized:
        return []
    entries = LSP_BACKEND_CATALOG.get(
        normalized,
        [
            {
                "backend_id": normalized,
                "label": f"{normalized} language support",
                "strategy_class": "project_required",
                "install_implemented": False,
                "recommended_scope": "instance",
                "tool_identity": None,
                "caveats": ["advisory metadata only; no install support is implemented"],
            }
        ],
    )
    options: list[dict[str, Any]] = []
    for entry in entries[:3]:
        item = dict(entry)
        host_tools = item.get("host_tools")
        if isinstance(host_tools, list):
            item["host_tool_visibility"] = {
                str(tool): shutil.which(str(tool)) is not None for tool in host_tools
            }
            item["host_tool_status"] = {str(tool): host_tool_status(str(tool)) for tool in host_tools}
        if language and language.strip().lower() != normalized:
            item["requested_language"] = language.strip().lower()
            item["normalized_language"] = normalized
        options.append(item)
    return options


def lsp_instance_scope(instance_dir: Path | None) -> dict[str, Any]:
    if instance_dir is None:
        return {"recommended_scope": "instance", "scaffold_present": False}
    lsp_tools = instance_dir / LSP_TOOLS_DIRNAME
    return {
        "recommended_scope": "instance",
        "instance_dir": str(instance_dir),
        "lsp_tools_dir": str(lsp_tools),
        "env_file": str(instance_dir / "lsp.env"),
        "manifest_path": str(lsp_tools / "manifest.json"),
        "scaffold_present": lsp_tools.is_dir() and (instance_dir / "lsp.env").is_file(),
    }


def base_lsp_advisory(language: str | None, instance_dir: Path | None) -> dict[str, Any]:
    options = lsp_backend_options(language)
    standard_provider = lsp_standard_provider(language, options)
    return {
        "lsp_capability_status": "advisory_not_probed",
        "lsp_gap_severity": LSP_GAP_NONE,
        "optional_capability_gaps": [],
        "lsp_backend_options": options,
        "lsp_standard_provider": standard_provider,
        "lsp_next_action": "keep_current_backend" if options else "select_language_before_lsp_advice",
        "lsp_instance_scope": lsp_instance_scope(instance_dir),
    }


def unsupported_optional_gap(capability: str, tool: str | None = None, detail: Any = None) -> dict[str, Any]:
    return {
        "capability": capability,
        "tool": tool,
        "classification": "unsupported_by_lsp_backend",
        "severity": LSP_GAP_OPTIONAL,
        "detail": detail,
    }


def classify_lsp_probe_response(capability: str, response: dict[str, Any], *, baseline: bool) -> dict[str, Any]:
    error = response.get("error")
    text = text_from_response(response)
    code = error.get("code") if isinstance(error, dict) else None
    unsupported = code == LSP_UNSUPPORTED_ERROR_CODE or str(LSP_UNSUPPORTED_ERROR_CODE) in text
    execution_error = "Error executing tool:" in text
    if unsupported:
        if baseline:
            return {
                "capability": capability,
                "classification": "baseline_lsp_method_missing",
                "severity": LSP_GAP_BASELINE,
                "ok": False,
                "detail": error or text[:1000],
            }
        return unsupported_optional_gap(capability, detail=error or text[:1000]) | {"ok": True}
    if error or execution_error:
        return {
            "capability": capability,
            "classification": "probe_error",
            "severity": LSP_GAP_BASELINE if baseline else LSP_GAP_RECOMMENDED,
            "ok": not baseline,
            "detail": error or text[:1000],
        }
    return {
        "capability": capability,
        "classification": "supported",
        "severity": LSP_GAP_NONE,
        "ok": True,
        "detail": text[:1000],
    }


def merge_lsp_advisory(
    advisory: dict[str, Any],
    *,
    status: str | None = None,
    severity: str | None = None,
    optional_gaps: list[dict[str, Any]] | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    merged = dict(advisory)
    if status is not None:
        merged["lsp_capability_status"] = status
    if severity is not None:
        merged["lsp_gap_severity"] = severity
    if optional_gaps is not None:
        merged["optional_capability_gaps"] = optional_gaps
    if next_action is not None:
        merged["lsp_next_action"] = next_action
    return merged


def socket_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.15)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def used_manifest_ports() -> set[int]:
    ports: set[int] = set()
    for manifest in (REPO_ROOT / "server-instances").glob("serena-*/instance.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        port = data.get("port") or (data.get("runtime") or {}).get("port")
        if isinstance(port, int):
            ports.add(port)
            continue
        url = str(data.get("mcp_url") or data.get("url") or "")
        parsed = urlparse(url)
        if parsed.port:
            ports.add(parsed.port)
    return ports


def existing_manifest_for_project(project_root: Path) -> dict[str, Any] | None:
    for manifest in (REPO_ROOT / "server-instances").glob("serena-*/instance.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        if manifest_project_root(data) == str(project_root):
            data["_manifest_path"] = str(manifest)
            return data
    return None


def related_serena_instances(project_root: Path) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []
    for manifest in (REPO_ROOT / "server-instances").glob("serena-*/instance.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        root_text = manifest_project_root(data)
        if not root_text:
            continue
        manifest_root = Path(root_text).expanduser().resolve(strict=False)
        relation: str | None = None
        try:
            project_root.relative_to(manifest_root)
            if project_root != manifest_root:
                relation = "ancestor"
        except ValueError:
            try:
                manifest_root.relative_to(project_root)
                if project_root != manifest_root:
                    relation = "descendant"
            except ValueError:
                relation = None
        if relation is None:
            continue
        identity = project_identity(manifest_root)
        related.append(
            {
                "relation": relation,
                "project_root": str(manifest_root),
                "instance_slug": str(data.get("instance_slug") or data.get("slug") or identity.instance_slug),
                "server_name": manifest_server_name(data, identity),
                "unit": manifest_unit_name(data, identity),
                "port": manifest_port(data),
                "manifest_path": str(manifest),
            }
        )
    return sorted(related, key=lambda item: (str(item["relation"]), str(item["project_root"])))


def manifest_project_root(data: dict[str, Any]) -> str | None:
    root = data.get("canonical_project_root")
    if isinstance(root, str) and root:
        return str(Path(root).expanduser().resolve(strict=False))

    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    root = scope.get("workspace_root")
    if isinstance(root, str) and root:
        return str(Path(root).expanduser().resolve(strict=False))

    backend = data.get("backend") if isinstance(data.get("backend"), dict) else {}
    args = backend.get("args")
    if isinstance(args, list):
        for index, item in enumerate(args):
            if item == "--project" and index + 1 < len(args) and isinstance(args[index + 1], str):
                return str(Path(args[index + 1]).expanduser().resolve(strict=False))

    return None


def reserve_port(preferred: int | None = None) -> int:
    used = used_manifest_ports()
    used.update(OPERATOR_RESERVED_PORTS)
    if preferred in OPERATOR_RESERVED_PORTS:
        raise RuntimeError(
            f"Serena port {preferred} is reserved for the operator singleton "
            "serena-context-portal and cannot be assigned to a per-project instance"
        )
    if preferred is not None and preferred not in used and not socket_port_open(preferred):
        return preferred
    for port in PORT_RANGE:
        if port in used:
            continue
        if socket_port_open(port):
            continue
        return port
    raise RuntimeError("no free Serena port in reserved range 9110-9199")


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def unit_name(instance_slug: str) -> str:
    return f"contextforge-{instance_slug}.service"


def unit_path(instance_slug: str) -> Path:
    return SYSTEMD_USER_DIR / unit_name(instance_slug)


def service_text(identity: Any, instance_dir: Path) -> str:
    return f"""[Unit]
Description=ContextForge Serena backend for {identity.root}
After=network.target contextforge-gateway.service
Wants=contextforge-gateway.service

[Service]
Type=simple
WorkingDirectory={REPO_ROOT}
Environment=PATH={SYSTEMD_PATH}
ExecStart={instance_dir}/run-server.sh
Restart=on-failure
RestartSec=3

[Install]
WantedBy=contextforge.target
"""


def run_server_text(identity: Any, port: int, instance_dir: Path) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
export SERENA_HOME="{instance_dir}/run/serena-home"
mkdir -p "$SERENA_HOME"
if [[ -f "{instance_dir}/lsp.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "{instance_dir}/lsp.env"
  set +a
fi
exec serena start-mcp-server \\
  --transport streamable-http \\
  --host 127.0.0.1 \\
  --port {port} \\
  --context codex \\
  --project "{identity.root}" \\
  --open-web-dashboard false
"""


def api_items(method: str, path: str, token: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return gateway._items(gateway._request(method, path, token=token, body=payload))


def gateway_by_name(gateways: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for item in gateways:
        if item.get("name") == name:
            return item
    return None


def server_by_name(servers: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for item in servers:
        if item.get("name") == name:
            return item
    return None


def prompt_ids(token: str) -> list[str]:
    ids: list[str] = []
    prompts = api_items("GET", "/prompts?include_inactive=true&limit=1000", token)
    for prompt in prompts:
        if prompt.get("name") == SERENA_GUIDANCE_PROMPT_NAME or prompt.get("customName") == SERENA_GUIDANCE_PROMPT_NAME:
            ids.append(str(prompt["id"]))
    return ids


def resource_ids(token: str) -> list[str]:
    ids: list[str] = []
    resources = api_items("GET", "/resources?include_inactive=true&limit=1000", token)
    for resource in resources:
        if resource.get("uri") == SERENA_GUIDANCE_RESOURCE_URI:
            ids.append(str(resource["id"]))
    return ids


def original_tool_name(tool: dict[str, Any], gateway_name: str | None = None) -> str:
    original = tool.get("originalName")
    if original:
        return str(original)
    name = str(tool.get("name") or "")
    if gateway_name and name.startswith(f"{gateway_name}-"):
        return name[len(gateway_name) + 1 :].replace("-", "_")
    return re.sub(r"^serena-.+?-[0-9a-f]{12}-", "", name).replace("-", "_")


def register_gateway_and_server(token: str, identity: Any, port: int) -> dict[str, Any]:
    mcp_url = f"http://127.0.0.1:{port}/mcp"
    gateway_name = identity.instance_slug
    gateways = api_items("GET", "/gateways?include_inactive=true&limit=1000", token)
    existing_gateway = gateway_by_name(gateways, gateway_name)
    gateway_payload = {
        "name": gateway_name,
        "url": mcp_url,
        "description": f"Serena MCP backend for {identity.root}",
        "transport": "STREAMABLEHTTP",
        "tags": ["serena", "project-instance", identity.slug, identity.hash],
        "visibility": VISIBILITY,
        "owner_email": OWNER,
        "gateway_mode": "cache",
        "passthroughHeaders": [],
    }
    if existing_gateway:
        update_payload = dict(gateway_payload)
        update_payload["enabled"] = True
        gateway_row = gateway._request("PUT", f"/gateways/{existing_gateway['id']}", token=token, body=update_payload)
    else:
        gateway_row = gateway._request("POST", "/gateways", token=token, body=gateway_payload)

    gateway_id = str(gateway_row.get("id") or (existing_gateway or {}).get("id"))
    try:
        gateway._request("POST", f"/gateways/{gateway_id}/tools/refresh", token=token)
    except Exception as exc:
        raise RuntimeError(f"gateway tool refresh failed for {gateway_name}: {exc}") from exc

    tools = []
    for _ in range(24):
        tools = [
            tool
            for tool in api_items("GET", "/tools?include_inactive=true&limit=1000", token)
            if tool.get("gatewayId") == gateway_id or tool.get("gateway_id") == gateway_id
        ]
        if tools:
            break
        time.sleep(1)
    allowed_tool_ids = [
        str(tool["id"])
        for tool in tools
        if original_tool_name(tool, gateway_name) not in EXCLUDED_ORIGINAL_TOOL_NAMES
    ]
    blocked = sorted(
        {
            original_tool_name(tool, gateway_name)
            for tool in tools
            if original_tool_name(tool, gateway_name) in EXCLUDED_ORIGINAL_TOOL_NAMES
        }
    )
    if not allowed_tool_ids:
        raise RuntimeError(f"no Serena tools discovered for {gateway_name}")
    if "activate_project" not in blocked:
        raise RuntimeError("expected activate_project to be discovered and filtered")

    servers = api_items("GET", "/servers?include_inactive=true&limit=1000", token)
    existing_server = server_by_name(servers, identity.server_name)
    server_payload = {
        "name": identity.server_name,
        "description": f"Project-pinned Serena tools for {identity.root}",
        "associated_tools": allowed_tool_ids,
        "associated_resources": resource_ids(token),
        "associated_prompts": prompt_ids(token),
        "tags": ["serena", "project-instance", identity.slug, identity.hash],
        "owner_email": OWNER,
        "visibility": VISIBILITY,
    }
    if existing_server:
        update_payload = {
            "associatedTools": allowed_tool_ids,
            "associatedResources": resource_ids(token),
            "associatedPrompts": prompt_ids(token),
            "associatedA2aAgents": existing_server.get("associatedA2aAgents") or [],
            "tags": ["serena", "project-instance", identity.slug, identity.hash],
            "ownerEmail": OWNER,
            "visibility": VISIBILITY,
        }
        server_row = gateway._request("PUT", f"/servers/{existing_server['id']}", token=token, body=update_payload)
    else:
        server_row = gateway._request("POST", "/servers", token=token, body={"server": server_payload, "visibility": VISIBILITY})

    server_id = str(server_row.get("id") or (existing_server or {}).get("id"))
    virtual_tools = api_items("GET", f"/servers/{server_id}/tools", token)
    virtual_names = {original_tool_name(tool, identity.server_name) for tool in virtual_tools}
    if "activate_project" in virtual_names:
        raise RuntimeError("activate_project is still exposed by the virtual server")
    if "get_current_config" not in virtual_names:
        raise RuntimeError("get_current_config missing after virtual server filtering")

    return {
        "gateway_id": gateway_id,
        "server_id": server_id,
        "tool_count": len(virtual_tools),
        "blocked_tools": blocked,
        "mcp_url": mcp_url,
    }


def codex_block(identity: Any) -> str:
    return f"""

# contextforge-project-init-owner = "{identity.server_name}"
[mcp_servers.serena]
command = "{PYTHON_PATH}"
args = ["{WRAPPER_PATH}", "{identity.server_name}"]
cwd = "{REPO_ROOT}"
startup_timeout_ms = 60000
tool_timeout_ms = 120000
""".lstrip()


def merge_codex_config(identity: Any, *, replace: bool = False) -> None:
    config_dir = identity.root / ".codex"
    config_path = config_dir / "config.toml"
    config_dir.mkdir(parents=True, exist_ok=True)
    block = codex_block(identity).rstrip() + "\n"
    if not config_path.exists():
        config_path.write_text(block, encoding="utf-8")
        return

    text = config_path.read_text(encoding="utf-8")
    section_re = re.compile(r"(?ms)^# contextforge-project-init-owner = \"[^\"]+\"\n\[mcp_servers\.serena\]\n.*?(?=^\[|\Z)")
    if section_re.search(text):
        config_path.write_text(section_re.sub(block, text).rstrip() + "\n", encoding="utf-8")
        return

    bare_section_re = re.compile(r"(?ms)^\[mcp_servers\.serena\]\n.*?(?=^\[|\Z)")
    bare = bare_section_re.search(text)
    if bare and not replace:
        raise RuntimeError(
            f"{config_path} already has an unmanaged [mcp_servers.serena]; rerun with --replace-existing-serena-config"
        )
    if bare and replace:
        config_path.write_text(bare_section_re.sub(block, text).rstrip() + "\n", encoding="utf-8")
        return

    config_path.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")


def verify_systemd_service(instance_slug: str) -> None:
    name = unit_name(instance_slug)
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "enable", name])
    run(["systemctl", "--user", "restart", name])
    deadline = time.time() + 25
    last = ""
    while time.time() < deadline:
        proc = run(["systemctl", "--user", "is-active", name], check=False, capture=True)
        last = proc.stdout.strip() or proc.stderr.strip()
        if proc.returncode == 0 and last == "active":
            return
        time.sleep(0.8)
    raise RuntimeError(f"{name} did not become active: {last}")


def wait_for_port(port: int) -> None:
    deadline = time.time() + 30
    while time.time() < deadline:
        if socket_port_open(port):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Serena port {port} did not open")


def ensure_path_under_instance(instance_dir: Path, path: Path) -> None:
    instance_real = instance_dir.resolve(strict=False)
    path_real = path.resolve(strict=False)
    try:
        path_real.relative_to(instance_real)
    except ValueError as exc:
        raise RuntimeError(f"LSP scaffold path escapes instance directory: {path}") from exc


def validate_lsp_scaffold_path(instance_dir: Path, path: Path) -> None:
    ensure_path_under_instance(instance_dir, path)
    current = path
    while current != instance_dir.parent and current != current.parent:
        if current.exists():
            if current.is_symlink():
                raise RuntimeError(f"LSP scaffold path must not be a symlink: {current}")
            mode = current.stat().st_mode
            if mode & stat.S_IWOTH:
                raise RuntimeError(f"LSP scaffold path must not be world-writable: {current}")
        if current == instance_dir:
            break
        current = current.parent


def validate_lsp_scaffold(instance_dir: Path) -> None:
    for relative in LSP_SCAFFOLD_DIRS:
        validate_lsp_scaffold_path(instance_dir, instance_dir / relative)
    validate_lsp_scaffold_path(instance_dir, instance_dir / "lsp.env")


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def ensure_lsp_scaffold(instance_dir: Path, language: str | None = None) -> dict[str, Any]:
    validate_lsp_scaffold_path(instance_dir, instance_dir)
    instance_dir.mkdir(parents=True, exist_ok=True)
    for relative in LSP_SCAFFOLD_DIRS:
        path = instance_dir / relative
        validate_lsp_scaffold_path(instance_dir, path)
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o755)

    lsp_tools = instance_dir / LSP_TOOLS_DIRNAME
    manifest_path = lsp_tools / "manifest.json"
    existing = read_json_file(manifest_path)
    manifest = existing | {
        "schema_version": 1,
        "scope": "instance",
        "install_implemented": False,
        "install_command_execution_enabled": install_command_execution_enabled(),
        "language": normalize_language_id(language),
        "backend_options": lsp_backend_options(language),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.chmod(0o644)

    env_path = instance_dir / "lsp.env"
    env_text = "\n".join(
        [
            f'PATH="{lsp_tools / "bin"}:$PATH"',
            f'XDG_CACHE_HOME="{lsp_tools / "cache" / "xdg"}"',
            f'SERENA_SOLIDLSP_HOME="{lsp_tools / "solidlsp"}"',
            f'SOLIDLSP_CACHE_DIR="{lsp_tools / "cache"}"',
            f'SOLIDLSP_LOG_DIR="{lsp_tools / "logs"}"',
            "",
        ]
    )
    env_path.write_text(env_text, encoding="utf-8")
    env_path.chmod(0o600)
    validate_lsp_scaffold(instance_dir)
    return {
        "created": True,
        "instance_dir": str(instance_dir),
        "lsp_tools_dir": str(lsp_tools),
        "manifest_path": str(manifest_path),
        "env_file": str(env_path),
    }


def manifest_instance_dir(manifest: dict[str, Any] | None, identity: Any) -> Path:
    if manifest and isinstance(manifest.get("_manifest_path"), str):
        return Path(str(manifest["_manifest_path"])).parent
    instance_slug = (manifest or {}).get("instance_slug") or (manifest or {}).get("slug") or identity.instance_slug
    return REPO_ROOT / "server-instances" / str(instance_slug)


def lsp_manifest_metadata(language: str | None, scaffold: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "advisory_status": "instance_scaffold_ready" if scaffold else "advisory_only",
        "install_implemented": False,
        "install_command_execution_enabled": install_command_execution_enabled(),
        "language": normalize_language_id(language),
        "backend_options": lsp_backend_options(language),
        "instance_scope": scaffold or {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_manifest(
    instance_dir: Path,
    identity: Any,
    port: int,
    registration: dict[str, Any] | None = None,
    lsp_metadata: dict[str, Any] | None = None,
) -> None:
    path = instance_dir / "instance.json"
    existing = read_json_file(path)
    existing_contextforge = existing.get("contextforge") if isinstance(existing.get("contextforge"), dict) else {}
    existing_gateway = existing_contextforge.get("gateway") if isinstance(existing_contextforge.get("gateway"), dict) else {}
    existing_virtual_server = (
        existing_contextforge.get("virtual_server")
        if isinstance(existing_contextforge.get("virtual_server"), dict)
        else {}
    )
    manifest_slug = str(existing_gateway.get("name") or existing.get("instance_slug") or existing.get("slug") or identity.instance_slug)
    manifest_server = str(existing_virtual_server.get("name") or existing.get("server_name") or identity.server_name)
    data = {
        "schema_version": 1,
        "service": "serena",
        "instance_slug": manifest_slug,
        "server_name": manifest_server,
        "canonical_project_root": str(identity.root),
        "project_root_hash": identity.root_hash,
        "slug": str(existing.get("slug") or identity.slug),
        "hash": str(existing.get("hash") or identity.hash),
        "unit": str(existing.get("unit") or unit_name(manifest_slug)),
        "port": port,
        "mcp_url": f"http://127.0.0.1:{port}/mcp",
        "codex_alias": "serena",
        "codex_config_path": str(identity.root / ".codex/config.toml"),
        "tool_policy": {
            "contextforge_excluded_original_tool_names": sorted(EXCLUDED_ORIGINAL_TOOL_NAMES),
            "single_project_mode": False,
            "source_level_exclusion": "not_applied_v1_contextforge_virtual_filter_is_authoritative",
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if registration:
        data["contextforge"] = registration
    elif existing_contextforge:
        data["contextforge"] = existing_contextforge
    if isinstance(existing.get("lsp"), dict) or lsp_metadata:
        existing_lsp = existing.get("lsp") if isinstance(existing.get("lsp"), dict) else {}
        data["lsp"] = existing_lsp | (lsp_metadata or {})
    for key, value in existing.items():
        if key not in data:
            data[key] = value
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def manifest_port(data: dict[str, Any]) -> int | None:
    port = data.get("port") or (data.get("runtime") or {}).get("port")
    if isinstance(port, int):
        return port

    bridge = data.get("bridge") if isinstance(data.get("bridge"), dict) else {}
    port = bridge.get("port")
    if isinstance(port, int):
        return port

    backend = data.get("backend") if isinstance(data.get("backend"), dict) else {}
    args = backend.get("args")
    if isinstance(args, list):
        for index, item in enumerate(args):
            if item == "--port" and index + 1 < len(args):
                try:
                    return int(args[index + 1])
                except (TypeError, ValueError):
                    return None

    for value in (
        data.get("mcp_url"),
        data.get("url"),
        bridge.get("streamable_http_url"),
        ((data.get("contextforge") or {}).get("gateway") or {}).get("url")
        if isinstance(data.get("contextforge"), dict)
        else None,
    ):
        if not value:
            continue
        parsed = urlparse(str(value))
        if parsed.port:
            return int(parsed.port)
    return None


def manifest_server_name(data: dict[str, Any], identity: Any) -> str:
    server_name = data.get("server_name")
    if isinstance(server_name, str) and server_name:
        return server_name
    contextforge = data.get("contextforge") if isinstance(data.get("contextforge"), dict) else {}
    virtual_server = contextforge.get("virtual_server") if isinstance(contextforge.get("virtual_server"), dict) else {}
    name = virtual_server.get("name")
    if isinstance(name, str) and name:
        return name
    return identity.server_name


def manifest_gateway_name(data: dict[str, Any], identity: Any) -> str:
    contextforge = data.get("contextforge") if isinstance(data.get("contextforge"), dict) else {}
    gateway_data = contextforge.get("gateway") if isinstance(contextforge.get("gateway"), dict) else {}
    name = gateway_data.get("name")
    if isinstance(name, str) and name:
        return name
    instance_slug = data.get("instance_slug") or data.get("slug") or data.get("name")
    return str(instance_slug or identity.instance_slug)


def manifest_unit_name(data: dict[str, Any], identity: Any) -> str:
    unit = data.get("unit")
    if isinstance(unit, str) and unit:
        return unit
    instance_slug = data.get("instance_slug") or data.get("slug") or data.get("name")
    return unit_name(str(instance_slug or identity.instance_slug))


def project_codex_serena_config(project_root: Path) -> dict[str, Any]:
    config_path = project_root / ".codex/config.toml"
    if not config_path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback is not expected here.
        return {}
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    return ((data.get("mcp_servers") or {}).get("serena") or {}) if isinstance(data, dict) else {}


def validate_language(language: str | None) -> str | None:
    normalized = normalize_language_id(language)
    if normalized is None:
        return None
    if normalized not in supported_languages():
        sample = ", ".join(RECOMMENDED_LANGUAGE_EXAMPLES)
        raise ValueError(f"unsupported Serena language {language!r}; examples: {sample}, ...")
    return normalized


def parse_languages_from_text(text: str) -> list[str] | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("languages:"):
            continue
        after = stripped.split(":", 1)[1].strip()
        if after == "[]":
            return []
        if after.startswith("[") and after.endswith("]"):
            values = after.removeprefix("[").removesuffix("]")
            return [item.strip().strip("'\"") for item in values.split(",") if item.strip()]
        languages: list[str] = []
        for child in lines[index + 1 :]:
            if not child.strip() or child.lstrip().startswith("#"):
                continue
            if child == child.lstrip():
                break
            child_stripped = child.strip()
            if child_stripped.startswith("- "):
                value = child_stripped[2:].strip().strip("'\"")
                if value:
                    languages.append(value)
        return languages
    return None


def read_languages_file(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    return parse_languages_from_text(path.read_text(encoding="utf-8"))


def configured_languages(project_root: Path) -> list[str]:
    serena_dir = project_root / ".serena"
    for path in (serena_dir / "project.local.yml", serena_dir / "project.yml"):
        languages = read_languages_file(path)
        if languages is not None:
            return languages
    return []


def replace_languages_block(text: str, languages: list[str]) -> str:
    replacement = "languages:\n" + "".join(f"  - {language}\n" for language in languages)
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    replaced = False
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith("languages:") and not replaced:
            output.extend(replacement.rstrip("\n").splitlines())
            replaced = True
            index += 1
            while index < len(lines):
                child = lines[index]
                if not child.strip() or child.lstrip().startswith("#"):
                    output.append(child)
                    index += 1
                    continue
                if child == child.lstrip():
                    break
                index += 1
            continue
        output.append(line)
        index += 1
    if not replaced:
        if output and output[-1].strip():
            output.append("")
        output.extend(replacement.rstrip("\n").splitlines())
    return "\n".join(output).rstrip() + "\n"


def write_language_override(project_root: Path, language: str) -> bool:
    normalized = validate_language(language)
    assert normalized is not None
    serena_dir = project_root / ".serena"
    serena_dir.mkdir(parents=True, exist_ok=True)
    local_path = serena_dir / "project.local.yml"
    text = local_path.read_text(encoding="utf-8") if local_path.exists() else (
        "# This file allows you to locally override Serena project settings.\n"
    )
    updated = replace_languages_block(text, [normalized])
    if local_path.exists() and local_path.read_text(encoding="utf-8") == updated:
        return False
    local_path.write_text(updated, encoding="utf-8")
    return True


def infer_language(project_root: Path) -> str | None:
    for marker, language in LANGUAGE_MARKERS:
        if (project_root / marker).exists():
            return language
    files = [
        path
        for path in project_root.rglob("*")
        if path.is_file() and not any(part in IGNORED_PROBE_DIRS for part in path.relative_to(project_root).parts[:-1])
    ]
    for language in LANGUAGE_INFERENCE_ORDER:
        suffixes = LANGUAGE_EXTENSIONS.get(language, ())
        if any(path.suffix in suffixes for path in files):
            return language
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_PROBE_DIRS for part in path.relative_to(project_root).parts[:-1]):
            continue
        for language, suffixes in LANGUAGE_EXTENSIONS.items():
            if path.suffix in suffixes:
                return language
    return None


def find_probe_target(project_root: Path, language: str) -> tuple[Path | None, bool]:
    suffixes = LANGUAGE_EXTENSIONS.get(language, ())
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(project_root).parts
        if any(part in IGNORED_PROBE_DIRS for part in relative_parts[:-1]):
            continue
        if path.suffix in suffixes:
            return path, False

    filename, content = LANGUAGE_PROBE_FILES.get(language, LANGUAGE_PROBE_FILES["python"])
    path = project_root / filename
    if path.exists():
        return path, False
    path.write_text(content, encoding="utf-8")
    return path, True


def language_examples() -> dict[str, Any]:
    return {
        "recommended_language_examples": list(RECOMMENDED_LANGUAGE_EXAMPLES),
        "supported_language_examples": sorted(SUPPORTED_LANGUAGES)[:16],
    }


def language_choice_command(project_root: Path, *, require_workspace: bool = True) -> str:
    parts = [
        str(PYTHON_PATH),
        str(Path(__file__).resolve()),
        "create",
        "--project-root",
        str(project_root),
    ]
    if require_workspace:
        parts.append("--require-workspace")
    parts.extend(["--language", "LANGUAGE", "--verify", "--app-server"])
    return " ".join(parts)


def language_state(project_root: Path, explicit_language: str | None = None, *, require_workspace: bool = True) -> dict[str, Any]:
    explicit = validate_language(explicit_language)
    if explicit:
        return {
            "language_status": "configured",
            "configured_languages": [explicit],
            "selected_language": explicit,
            "needs_user_language_choice": False,
            **language_examples(),
        }

    configured = configured_languages(project_root)
    if configured:
        return {
            "language_status": "configured",
            "configured_languages": configured,
            "selected_language": configured[0],
            "needs_user_language_choice": False,
            **language_examples(),
        }

    inferred = infer_language(project_root)
    if inferred:
        return {
            "language_status": "detected",
            "configured_languages": [],
            "selected_language": inferred,
            "needs_user_language_choice": False,
            **language_examples(),
        }

    return {
        "language_status": "needs_language",
        "configured_languages": configured,
        "selected_language": None,
        "needs_user_language_choice": True,
        "next_action": "ask_user_for_serena_language_before_create",
        "recommended_command": language_choice_command(project_root, require_workspace=require_workspace),
        **language_examples(),
    }


def restart_project_service(unit: str) -> None:
    run(["systemctl", "--user", "restart", unit])
    deadline = time.time() + 25
    while time.time() < deadline:
        proc = run(["systemctl", "--user", "is-active", unit], check=False, capture=True)
        if proc.returncode == 0 and proc.stdout.strip() == "active":
            return
        time.sleep(0.8)
    raise RuntimeError(f"{unit} did not become active after language update")


def text_from_response(value: Any) -> str:
    chunks: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, str):
            chunks.append(item)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            for key in ("text", "content", "result", "message", "output"):
                if key in item:
                    walk(item[key])

    walk(value)
    return "\n".join(chunks)


def app_server_servers(status_response: dict[str, Any]) -> list[dict[str, Any]]:
    result = status_response.get("result")
    if isinstance(result, dict):
        servers = result.get("servers") or result.get("data") or []
    elif isinstance(result, list):
        servers = result
    else:
        servers = []
    return [server for server in servers if isinstance(server, dict)]


def app_server_tool_names(server: dict[str, Any]) -> list[str]:
    tools_payload = server.get("tools") or []
    tools = list(tools_payload.values()) if isinstance(tools_payload, dict) else tools_payload
    return [str(tool.get("name") or "") for tool in tools if isinstance(tool, dict)]


def app_server_probe(
    project_root: Path,
    expected_project_name: str,
    language: str | None,
    *,
    probe_optional_lsp: bool = False,
    instance_dir: Path | None = None,
) -> dict[str, Any]:
    proc = subprocess.Popen(
        ["codex", "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=project_root,
    )
    next_id = 0
    created_probe: Path | None = None

    def send(method: str, params: dict[str, Any] | None = None, *, notify: bool = False) -> int | None:
        nonlocal next_id
        obj: dict[str, Any] = {"method": method}
        if params is not None:
            obj["params"] = params
        if not notify:
            obj["id"] = next_id
            next_id += 1
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
        proc.stdin.flush()
        return obj.get("id")

    def read(expect_id: int, timeout: int = 30) -> dict[str, Any]:
        assert proc.stdout is not None
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready, _, _ = select.select([proc.stdout], [], [], max(0, deadline - time.time()))
            if not ready:
                break
            raw = proc.stdout.readline()
            if not raw:
                break
            msg = json.loads(raw)
            if msg.get("id") == expect_id:
                return msg
        stderr = ""
        if proc.stderr is not None:
            try:
                ready_err, _, _ = select.select([proc.stderr], [], [], 0)
                if ready_err:
                    stderr = proc.stderr.read()
            except Exception:
                stderr = ""
        raise TimeoutError(f"missing app-server response {expect_id}; stderr={stderr[:500]}")

    def call(
        method: str,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        *,
        allow_error: bool = False,
    ) -> dict[str, Any]:
        request_id = send(method, params)
        assert request_id is not None
        response = read(request_id, timeout)
        if "error" in response and not allow_error:
            raise RuntimeError(f"{method} failed: {response['error']}")
        return response

    try:
        call(
            "initialize",
            {
                "clientInfo": {"name": "serena-manager-verify", "title": None, "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            },
            10,
        )
        send("initialized", notify=True)
        thread = call(
            "thread/start",
            {
                "cwd": str(project_root),
                "ephemeral": True,
                "approvalPolicy": "never",
                "sandbox": "danger-full-access",
            },
            25,
        )
        thread_info = (thread.get("result") or {}).get("thread") or {}
        thread_id = thread_info["id"]
        status = call(
            "mcpServerStatus/list",
            {"threadId": thread_id, "detail": "toolsAndAuthOnly"},
            60,
        )
        servers = app_server_servers(status)
        if not servers:
            raise RuntimeError("mcpServerStatus/list did not return a server list")
        serena = next((server for server in servers if server.get("name") == "serena"), None)
        if not serena:
            raise RuntimeError("app-server did not expose a serena MCP server")
        tool_names = app_server_tool_names(serena)
        if any("activate" in name for name in tool_names):
            raise RuntimeError("app-server exposed an activate tool")
        get_config_tool = next((name for name in tool_names if name.endswith("get-current-config")), None)
        diagnostics_tool = next((name for name in tool_names if name.endswith("get-diagnostics-for-file")), None)
        symbols_tool = next((name for name in tool_names if name.endswith("get-symbols-overview")), None)
        implementations_tool = next((name for name in tool_names if name.endswith("find-implementations")), None)
        if not get_config_tool:
            raise RuntimeError("app-server tool list is missing get-current-config")
        if not diagnostics_tool and not symbols_tool:
            raise RuntimeError("app-server tool list is missing diagnostics and symbols tools")

        config_response = call(
            "mcpServer/tool/call",
            {"threadId": thread_id, "server": "serena", "tool": get_config_tool, "arguments": {}},
            90,
        )
        config_text = text_from_response(config_response)
        if f"Active project: {expected_project_name}" not in config_text:
            raise RuntimeError(f"get-current-config did not report active project {expected_project_name!r}")
        if "Language backend: LSP" not in config_text:
            raise RuntimeError("get-current-config did not report LSP backend")

        lsp_tool = diagnostics_tool or symbols_tool
        lsp_status = "skipped_needs_language"
        lsp_response_text = ""
        lsp_probe_path = None
        optional_lsp_results: list[dict[str, Any]] = []
        optional_capability_gaps: list[dict[str, Any]] = []
        advisory = base_lsp_advisory(language, instance_dir)
        if language:
            probe_path, created = find_probe_target(project_root, language)
            if probe_path is None:
                lsp_status = "lsp_unavailable"
                advisory = merge_lsp_advisory(
                    advisory,
                    status="baseline_unavailable",
                    severity=LSP_GAP_BASELINE,
                    next_action="select_supported_language_or_backend",
                )
            else:
                created_probe = probe_path if created else None
                relative_path = str(probe_path.relative_to(project_root))
                if relative_path in {"", "."}:
                    raise RuntimeError("refusing directory LSP probe path")
                lsp_args = {"relative_path": relative_path}
                lsp_response = call(
                    "mcpServer/tool/call",
                    {"threadId": thread_id, "server": "serena", "tool": lsp_tool, "arguments": lsp_args},
                    90,
                )
                baseline_result = classify_lsp_probe_response(
                    "baseline_read_only_lsp_probe",
                    lsp_response,
                    baseline=True,
                )
                lsp_status = "verified" if baseline_result.get("ok") else "baseline_probe_failed"
                lsp_response_text = text_from_response(lsp_response)[:1000]
                lsp_probe_path = relative_path
                if baseline_result.get("ok"):
                    advisory = merge_lsp_advisory(
                        advisory,
                        status="baseline_verified",
                        severity=LSP_GAP_NONE,
                        next_action="keep_current_backend",
                    )
                else:
                    advisory = merge_lsp_advisory(
                        advisory,
                        status="baseline_probe_failed",
                        severity=LSP_GAP_BASELINE,
                        next_action="repair_lsp_backend_before_claiming_setup",
                    )
                if probe_optional_lsp and baseline_result.get("ok"):
                    if implementations_tool:
                        optional_args = {"name_path": "contextforge_serena_probe", "relative_path": relative_path}
                        optional_response = call(
                            "mcpServer/tool/call",
                            {
                                "threadId": thread_id,
                                "server": "serena",
                                "tool": implementations_tool,
                                "arguments": optional_args,
                            },
                            90,
                            allow_error=True,
                        )
                        classified = classify_lsp_probe_response(
                            "find_implementations",
                            optional_response,
                            baseline=False,
                        )
                        classified["tool"] = implementations_tool
                        optional_lsp_results.append(classified)
                        if classified.get("classification") == "unsupported_by_lsp_backend":
                            optional_capability_gaps.append(classified)
                    else:
                        gap = unsupported_optional_gap("find_implementations", "find-implementations", "tool_not_exposed")
                        optional_lsp_results.append(gap | {"ok": True})
                        optional_capability_gaps.append(gap)
                    if optional_capability_gaps:
                        advisory = merge_lsp_advisory(
                            advisory,
                            status="baseline_verified_with_optional_gaps",
                            severity=LSP_GAP_OPTIONAL,
                            optional_gaps=optional_capability_gaps,
                            next_action="report_optional_gap_without_failing_setup",
                        )
                    elif any(item.get("severity") == LSP_GAP_RECOMMENDED for item in optional_lsp_results):
                        advisory = merge_lsp_advisory(
                            advisory,
                            status="baseline_verified_with_advisory_probe_notes",
                            severity=LSP_GAP_RECOMMENDED,
                            next_action="keep_current_backend",
                        )
        return {
            "thread_id": thread_id,
            "tool_count": len(tool_names),
            "has_activate_tool": any("activate" in name for name in tool_names),
            "active_project_ok": f"Active project: {expected_project_name}" in config_text,
            "get_current_config_tool": get_config_tool,
            "lsp_status": lsp_status,
            "lsp_tool": lsp_tool,
            "lsp_probe_path": lsp_probe_path,
            "lsp_response_text": lsp_response_text,
            "baseline_lsp_result": baseline_result if language and lsp_probe_path else None,
            "optional_lsp_results": optional_lsp_results,
            **advisory,
        }
    finally:
        if created_probe is not None:
            created_probe.unlink(missing_ok=True)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def build_verify_result(args: argparse.Namespace) -> dict[str, Any]:
    language = validate_language(getattr(args, "language", None))
    project_root = validate_project_root(args.project_root, require_workspace=args.require_workspace)
    identity = project_identity(project_root)
    result: dict[str, Any] = {
        "project_root": str(project_root),
        "deterministic_identity": {
            "instance_slug": identity.instance_slug,
            "server_name": identity.server_name,
            "hash": identity.hash,
        },
        "checks": {},
        "errors": [],
    }
    initial_language_info = language_state(project_root, language, require_workspace=args.require_workspace)
    result.update(initial_language_info)
    result.update(base_lsp_advisory(initial_language_info.get("selected_language"), REPO_ROOT / "server-instances" / identity.instance_slug))

    def check(name: str, condition: bool, detail: Any = None) -> None:
        result["checks"][name] = {"ok": bool(condition), "detail": detail}
        if not condition:
            result["errors"].append(name)

    manifest = existing_manifest_for_project(project_root)
    check("manifest_exists", manifest is not None, (manifest or {}).get("_manifest_path"))
    if not manifest:
        result["ok"] = False
        return result

    port = manifest_port(manifest)
    server_name = manifest_server_name(manifest, identity)
    gateway_name = manifest_gateway_name(manifest, identity)
    unit = manifest_unit_name(manifest, identity)
    instance_dir = manifest_instance_dir(manifest, identity)

    if language:
        changed = write_language_override(project_root, language)
        if changed:
            restart_project_service(unit)

    language_info = language_state(project_root, language, require_workspace=args.require_workspace)
    result.update(language_info)
    result.update(base_lsp_advisory(language_info.get("selected_language"), instance_dir))

    result["runtime"] = {
        "manifest_path": manifest.get("_manifest_path"),
        "server_name": server_name,
        "gateway_name": gateway_name,
        "unit": unit,
        "port": port,
    }
    check("manifest_project_root_matches", manifest_project_root(manifest) == str(project_root), manifest_project_root(manifest))
    check("port_open", isinstance(port, int) and socket_port_open(port), port)

    unit_state = run(["systemctl", "--user", "is-active", unit], check=False, capture=True)
    unit_active = unit_state.stdout.strip() or unit_state.stderr.strip()
    check("unit_active", unit_state.returncode == 0 and unit_active == "active", {"unit": unit, "state": unit_active})

    env = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])

    prompts = api_items("GET", "/prompts?include_inactive=true&limit=1000", token)
    resources = api_items("GET", "/resources?include_inactive=true&limit=1000", token)
    project_prompt_count = sum(
        1 for prompt in prompts if prompt.get("name") == PROJECT_INIT_PROMPT_NAME or prompt.get("customName") == PROJECT_INIT_PROMPT_NAME
    )
    serena_prompt_count = sum(
        1 for prompt in prompts if prompt.get("name") == SERENA_GUIDANCE_PROMPT_NAME or prompt.get("customName") == SERENA_GUIDANCE_PROMPT_NAME
    )
    project_resource_count = sum(1 for resource in resources if resource.get("uri") == PROJECT_INIT_RESOURCE_URI)
    serena_resource_count = sum(1 for resource in resources if resource.get("uri") == SERENA_GUIDANCE_RESOURCE_URI)
    check("project_init_prompt_count", project_prompt_count == 1, project_prompt_count)
    check("project_init_resource_count", project_resource_count == 1, project_resource_count)
    check("serena_guidance_prompt_count", serena_prompt_count == 1, serena_prompt_count)
    check("serena_guidance_resource_count", serena_resource_count == 1, serena_resource_count)

    gateways = api_items("GET", "/gateways?include_inactive=true&limit=1000", token)
    gateway_row = gateway_by_name(gateways, gateway_name)
    gateway_port = urlparse(str((gateway_row or {}).get("url") or "")).port if gateway_row else None
    check("contextforge_gateway_exists", gateway_row is not None, {"name": gateway_name, "port": gateway_port})
    check("contextforge_gateway_points_to_port", gateway_port == port, {"expected": port, "actual": gateway_port})

    servers = api_items("GET", "/servers?include_inactive=true&limit=1000", token)
    server = server_by_name(servers, server_name)
    check("contextforge_virtual_server_exists", server is not None, server_name)
    virtual_tools = api_items("GET", f"/servers/{server['id']}/tools", token) if server else []
    original_names = {original_tool_name(tool, gateway_name) for tool in virtual_tools}
    tool_names = {str(tool.get("name") or "") for tool in virtual_tools}
    check("virtual_server_excludes_activate_project", "activate_project" not in original_names, sorted(tool_names))
    check("virtual_server_has_get_current_config", "get_current_config" in original_names, sorted(original_names))
    check(
        "virtual_server_has_lsp_tool",
        bool({"get_diagnostics_for_file", "get_symbols_overview"} & original_names),
        sorted(original_names),
    )

    serena_config = project_codex_serena_config(project_root)
    check("project_codex_serena_command", serena_config.get("command") == str(PYTHON_PATH), serena_config)
    check(
        "project_codex_serena_args",
        serena_config.get("args") == [str(WRAPPER_PATH), server_name],
        serena_config.get("args"),
    )
    check("project_codex_serena_cwd", serena_config.get("cwd") == str(REPO_ROOT), serena_config.get("cwd"))

    home_lookup = subprocess.run(
        ["codex", "mcp", "get", "serena"],
        cwd=Path.home(),
        text=True,
        capture_output=True,
        check=False,
    )
    check("codex_home_serena_absent", home_lookup.returncode != 0, home_lookup.stderr.strip() or home_lookup.stdout.strip())
    project_lookup = subprocess.run(
        ["codex", "mcp", "get", "serena"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    check("codex_project_serena_present", project_lookup.returncode == 0 and server_name in project_lookup.stdout, project_lookup.stdout or project_lookup.stderr)

    if args.app_server:
        try:
            app_probe = app_server_probe(
                project_root,
                project_root.name,
                language_info.get("selected_language"),
                probe_optional_lsp=getattr(args, "probe_optional_lsp", False),
                instance_dir=instance_dir,
            )
            result["app_server_probe"] = app_probe
            for key in (
                "lsp_capability_status",
                "lsp_gap_severity",
                "optional_capability_gaps",
                "lsp_backend_options",
                "lsp_standard_provider",
                "lsp_next_action",
                "lsp_instance_scope",
            ):
                if key in app_probe:
                    result[key] = app_probe[key]
            result["language_status"] = app_probe.get("lsp_status") if app_probe.get("lsp_status") == "lsp_unavailable" else result["language_status"]
            check("app_server_serena_runtime", app_probe.get("lsp_gap_severity") != LSP_GAP_BASELINE, app_probe)
        except Exception as exc:
            result.update(
                merge_lsp_advisory(
                    base_lsp_advisory(language_info.get("selected_language"), instance_dir),
                    status="baseline_probe_failed",
                    severity=LSP_GAP_BASELINE,
                    next_action="repair_lsp_backend_before_claiming_setup",
                )
            )
            check("app_server_serena_runtime", False, str(exc))

    ok = not result["errors"]
    result["ok"] = ok
    return result


def verify(args: argparse.Namespace) -> int:
    result = build_verify_result(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


def create(args: argparse.Namespace) -> int:
    language = validate_language(getattr(args, "language", None))
    identity = project_identity(validate_project_root(args.project_root, require_workspace=args.require_workspace))
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        existing = existing_manifest_for_project(identity.root)
        if existing and isinstance(existing.get("port"), int):
            port = int(existing["port"])
        else:
            port = reserve_port()

        instance_dir = REPO_ROOT / "server-instances" / identity.instance_slug
        instance_dir.mkdir(parents=True, exist_ok=True)
        (instance_dir / "run").mkdir(exist_ok=True)
        scaffold = ensure_lsp_scaffold(instance_dir, language)
        write_executable(instance_dir / "run-server.sh", run_server_text(identity, port, instance_dir))
        write_manifest(instance_dir, identity, port, lsp_metadata=lsp_manifest_metadata(language, scaffold))
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
        unit_path(identity.instance_slug).write_text(service_text(identity, instance_dir), encoding="utf-8")

    verify_systemd_service(identity.instance_slug)
    wait_for_port(port)
    if language:
        write_language_override(identity.root, language)
        restart_project_service(unit_name(identity.instance_slug))
        wait_for_port(port)

    env = gateway._read_env(gateway.CONFIG_ENV)
    token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
    registration = register_gateway_and_server(token, identity, port)
    scaffold = ensure_lsp_scaffold(instance_dir, language)
    write_manifest(instance_dir, identity, port, registration, lsp_metadata=lsp_manifest_metadata(language, scaffold))
    if getattr(args, "write_codex_config", True):
        merge_codex_config(identity, replace=args.replace_existing_serena_config)
    write_project_env(
        identity.root,
        {
            ENV_SERENA_DECISION: "accepted",
            ENV_SERENA_PROVISION_STATUS: "created",
            ENV_SERENA_INSTANCE_SLUG: identity.instance_slug,
            ENV_SERENA_SERVER_NAME: identity.server_name,
            ENV_PROJECT_INIT_STATUS: "complete",
        },
    )
    output: dict[str, Any] = {
        "project_root": str(identity.root),
        "instance_slug": identity.instance_slug,
        "server_name": identity.server_name,
        "port": port,
        "registration": registration,
        **base_lsp_advisory(language_state(identity.root, language, require_workspace=args.require_workspace).get("selected_language"), instance_dir),
        **language_state(identity.root, language, require_workspace=args.require_workspace),
    }
    if getattr(args, "verify", False):
        verify_args = argparse.Namespace(
            project_root=str(identity.root),
            require_workspace=args.require_workspace,
            app_server=getattr(args, "app_server", False),
            probe_optional_lsp=False,
            language=language,
        )
        output["verification"] = build_verify_result(verify_args)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def status(args: argparse.Namespace) -> int:
    identity = project_identity(validate_project_root(args.project_root, require_workspace=args.require_workspace))
    manifest = existing_manifest_for_project(identity.root)
    unit = manifest_unit_name(manifest, identity) if manifest else unit_name(identity.instance_slug)
    port = manifest_port(manifest) if manifest else None
    server_name = manifest_server_name(manifest, identity) if manifest else identity.server_name
    lang = language_state(identity.root, getattr(args, "language", None), require_workspace=args.require_workspace)
    instance_dir = manifest_instance_dir(manifest, identity) if manifest else REPO_ROOT / "server-instances" / identity.instance_slug
    result = {
        "project_root": str(identity.root),
        "env_present": (identity.root / ".env").exists(),
        "identity": {
            "instance_slug": identity.instance_slug,
            "server_name": identity.server_name,
            "hash": identity.hash,
        },
        "manifest": manifest,
        "related_instances": related_serena_instances(identity.root),
        "runtime": {"unit": unit, "port": port, "server_name": server_name},
        "port_open": isinstance(port, int) and socket_port_open(port),
        **lang,
        **base_lsp_advisory(lang.get("selected_language"), instance_dir),
        "unit_active": None,
    }
    proc = run(["systemctl", "--user", "is-active", unit], check=False, capture=True)
    result["unit_active"] = proc.stdout.strip() if proc.stdout.strip() else proc.stderr.strip()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def refresh_lsp_scaffold(args: argparse.Namespace) -> int:
    language = validate_language(getattr(args, "language", None))
    identity = project_identity(validate_project_root(args.project_root, require_workspace=args.require_workspace))
    manifest = existing_manifest_for_project(identity.root)
    if not manifest:
        raise RuntimeError("no Serena instance manifest exists for this project")
    port = manifest_port(manifest)
    if not isinstance(port, int):
        raise RuntimeError("Serena instance manifest has no usable port")
    selected_language = language or language_state(identity.root, None, require_workspace=args.require_workspace).get("selected_language")
    instance_dir = manifest_instance_dir(manifest, identity)
    scaffold = ensure_lsp_scaffold(instance_dir, selected_language)
    write_manifest(instance_dir, identity, port, lsp_metadata=lsp_manifest_metadata(selected_language, scaffold))
    run_server = instance_dir / "run-server.sh"
    if run_server.exists():
        write_executable(run_server, run_server_text(identity, port, instance_dir))
    print(json.dumps({"project_root": str(identity.root), "scaffold": scaffold, **base_lsp_advisory(selected_language, instance_dir)}, indent=2, sort_keys=True))
    return 0


def probe_lsp_capabilities(args: argparse.Namespace) -> int:
    language = validate_language(getattr(args, "language", None))
    identity = project_identity(validate_project_root(args.project_root, require_workspace=args.require_workspace))
    manifest = existing_manifest_for_project(identity.root)
    instance_dir = manifest_instance_dir(manifest, identity) if manifest else REPO_ROOT / "server-instances" / identity.instance_slug
    selected_language = language or language_state(identity.root, None, require_workspace=args.require_workspace).get("selected_language")
    if not args.app_server:
        raise RuntimeError("probe-lsp-capabilities requires --app-server so the actual Codex path is used")
    result = app_server_probe(
        identity.root,
        identity.root.name,
        selected_language,
        probe_optional_lsp=True,
        instance_dir=instance_dir,
    )
    print(json.dumps({"project_root": str(identity.root), **result}, indent=2, sort_keys=True))
    return 0


def remove(args: argparse.Namespace) -> int:
    if not args.yes:
        raise RuntimeError("remove requires --yes")
    identity = project_identity(validate_project_root(args.project_root, require_workspace=False))
    deleted_contextforge: dict[str, str | None] = {"server_id": None, "gateway_id": None}
    if args.delete_contextforge_records:
        env = gateway._read_env(gateway.CONFIG_ENV)
        token = gateway._token(env["PLATFORM_ADMIN_EMAIL"], env["PLATFORM_ADMIN_PASSWORD"])
        servers = api_items("GET", "/servers?include_inactive=true&limit=1000", token)
        server = server_by_name(servers, identity.server_name)
        if server:
            gateway._request("DELETE", f"/servers/{server['id']}", token=token)
            deleted_contextforge["server_id"] = str(server["id"])
        gateways = api_items("GET", "/gateways?include_inactive=true&limit=1000", token)
        gateway_row = gateway_by_name(gateways, identity.instance_slug)
        if gateway_row:
            gateway._request("DELETE", f"/gateways/{gateway_row['id']}", token=token)
            deleted_contextforge["gateway_id"] = str(gateway_row["id"])
    name = unit_name(identity.instance_slug)
    run(["systemctl", "--user", "disable", "--now", name], check=False)
    unit_path(identity.instance_slug).unlink(missing_ok=True)
    run(["systemctl", "--user", "daemon-reload"], check=False)
    if args.delete_instance_dir:
        shutil.rmtree(REPO_ROOT / "server-instances" / identity.instance_slug, ignore_errors=True)
    write_project_env(
        identity.root,
        {
            ENV_SERENA_PROVISION_STATUS: "removed",
        },
    )
    print(json.dumps({"removed_unit": name, "project_root": str(identity.root), "contextforge_deleted": deleted_contextforge}, indent=2, sort_keys=True))
    return 0


def identity_cmd(args: argparse.Namespace) -> int:
    identity = project_identity(validate_project_root(args.project_root, require_workspace=False))
    print(json.dumps(identity.__dict__ | {"root": str(identity.root)}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    identity = sub.add_parser("identity", help="Print deterministic Serena identity for a project.")
    identity.add_argument("--project-root", required=True)
    identity.set_defaults(func=identity_cmd)

    status_parser = sub.add_parser("status", help="Show current Serena instance state for a project.")
    status_parser.add_argument("--project-root", required=True)
    status_parser.add_argument("--require-workspace", action="store_true", help="Require a safe /home/dgk/workspace child root.")
    status_parser.add_argument("--language", help="Explicit Serena language to report for empty-project planning.")
    status_parser.set_defaults(func=status)

    verify_parser = sub.add_parser("verify", help="Verify a project Serena backend through systemd, ContextForge, Codex config, and optionally app-server.")
    verify_parser.add_argument("--project-root", required=True)
    verify_parser.add_argument("--require-workspace", action="store_true", help="Require a safe /home/dgk/workspace child root.")
    verify_parser.add_argument("--app-server", action="store_true", help="Also verify the actual Codex app-server MCP call path.")
    verify_parser.add_argument("--probe-optional-lsp", action="store_true", help="Probe optional read-only LSP capabilities without failing setup on unsupported methods.")
    verify_parser.add_argument("--language", help="Explicit Serena language for empty-project LSP verification.")
    verify_parser.add_argument(
        "--diagnostics-path",
        default="scripts/contextforge_mcp_wrapper.py",
        help=argparse.SUPPRESS,
    )
    verify_parser.set_defaults(func=verify)

    create_parser = sub.add_parser("create", help="Create or refresh the project Serena backend.")
    create_parser.add_argument("--project-root", required=True)
    create_parser.add_argument("--require-workspace", action="store_true", help="Require a safe /home/dgk/workspace child root.")
    create_parser.add_argument("--replace-existing-serena-config", action="store_true")
    create_parser.add_argument("--language", help="Explicit Serena language for empty-project LSP verification.")
    create_parser.add_argument("--verify", action="store_true", help="Run manager verification after create.")
    create_parser.add_argument("--app-server", action="store_true", help="With --verify, include Codex app-server MCP calls.")
    create_parser.set_defaults(write_codex_config=True)
    create_parser.set_defaults(func=create)

    scaffold_parser = sub.add_parser("refresh-lsp-scaffold", help="Create or repair instance-local advisory LSP scaffolding.")
    scaffold_parser.add_argument("--project-root", required=True)
    scaffold_parser.add_argument("--require-workspace", action="store_true", help="Require a safe /home/dgk/workspace child root.")
    scaffold_parser.add_argument("--language", help="Explicit Serena language for advisory metadata.")
    scaffold_parser.set_defaults(func=refresh_lsp_scaffold)

    probe_parser = sub.add_parser("probe-lsp-capabilities", help="Probe read-only optional LSP capabilities through the Codex app-server path.")
    probe_parser.add_argument("--project-root", required=True)
    probe_parser.add_argument("--require-workspace", action="store_true", help="Require a safe /home/dgk/workspace child root.")
    probe_parser.add_argument("--app-server", action="store_true", help="Required; use the actual Codex app-server MCP path.")
    probe_parser.add_argument("--language", help="Explicit Serena language for LSP probing.")
    probe_parser.set_defaults(func=probe_lsp_capabilities)

    remove_parser = sub.add_parser("remove", help="Stop and optionally delete a project Serena backend.")
    remove_parser.add_argument("--project-root", required=True)
    remove_parser.add_argument("--yes", action="store_true")
    remove_parser.add_argument("--delete-instance-dir", action="store_true")
    remove_parser.add_argument("--delete-contextforge-records", action="store_true")
    remove_parser.set_defaults(func=remove)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
