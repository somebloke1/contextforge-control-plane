#!/usr/bin/env python3
"""Shared helpers for ContextForge project initialization."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


HOME = Path.home().resolve()
WORKSPACE_ROOT = Path("/home/dgk/workspace").resolve()
CMU_MATH_FOUNDATIONS_ROOT = Path("/home/dgk/gdrive/__CMU/classes/00_MathFoundationsML").resolve()
SAFE_PROJECT_ROOTS = frozenset({WORKSPACE_ROOT, CMU_MATH_FOUNDATIONS_ROOT})
ADDITIONAL_SAFE_ROOTS_ENV = "CONTEXTFORGE_ADDITIONAL_SAFE_PROJECT_ROOTS"
REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = Path(os.environ.get("CONTEXTFORGE_PROJECT_INIT_RUN_ROOT", REPO_ROOT / "run")).expanduser().resolve(strict=False)
SERVER_INSTANCES_ROOT = REPO_ROOT / "server-instances"
WRAPPER_PATH = REPO_ROOT / "scripts" / "contextforge_mcp_wrapper.py"
PYTHON_PATH = REPO_ROOT / ".venv" / "bin" / "python"

PROMPT_VERSION = "v16"
PROJECT_INIT_PROMPT_NAME = "project_init_prompt"
PROJECT_INIT_RESOURCE_NAME = f"project_init_resource_{PROMPT_VERSION}"
PROJECT_INIT_RESOURCE_URI = f"contextforge://cf-controlplane/project-init/{PROMPT_VERSION}"
SERENA_GUIDANCE_PROMPT_NAME = "serena_project_instance_guidance"
SERENA_GUIDANCE_RESOURCE_NAME = f"serena_project_instance_guidance_resource_{PROMPT_VERSION}"
SERENA_GUIDANCE_RESOURCE_URI = f"contextforge://cf-controlplane/serena-project-instance-guidance/{PROMPT_VERSION}"

ENV_PROJECT_INIT_STATUS = "CONTEXTFORGE_PROJECT_INIT_DIALOGUE_STATUS"
ENV_SERENA_DECISION = "CONTEXTFORGE_SERENA_DECISION"
ENV_SERENA_PROVISION_STATUS = "CONTEXTFORGE_SERENA_PROVISION_STATUS"
ENV_SERENA_INSTANCE_SLUG = "CONTEXTFORGE_SERENA_INSTANCE_SLUG"
ENV_SERENA_SERVER_NAME = "CONTEXTFORGE_SERENA_SERVER_NAME"
ENV_USE_DEV_DOCKER_VIRTUAL_SERVER = "CONTEXTFORGE_PROJECT_INIT_USE_DEV_DOCKER_VIRTUAL_SERVER"

PROJECT_ENV_KEYS = {
    ENV_PROJECT_INIT_STATUS,
    ENV_SERENA_DECISION,
    ENV_SERENA_PROVISION_STATUS,
    ENV_SERENA_INSTANCE_SLUG,
    ENV_SERENA_SERVER_NAME,
}

PROJECT_INIT_ACTIVE_STATES = {"unasked", "asked"}
PROJECT_INIT_TERMINAL_STATES = {"complete", "disabled"}
SERENA_DECISION_STATES = {"unasked", "accepted", "declined", "disabled"}
SERENA_PROVISION_STATES = {"none", "pending", "created", "failed", "removed"}

DENIED_PROJECT_ROOTS = {
    Path("/").resolve(),
    HOME,
    WORKSPACE_ROOT,
}

PROJECT_MARKERS = (
    ".git",
    ".codex",
    ".opencode",
    ".env",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "uv.lock",
    "README.md",
)


@dataclass(frozen=True)
class ProjectIdentity:
    root: Path
    slug: str
    hash: str
    instance_slug: str
    server_name: str
    root_hash: str


def canonical_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def additional_safe_project_roots() -> frozenset[Path]:
    raw = os.environ.get(ADDITIONAL_SAFE_ROOTS_ENV, "")
    roots = {
        canonical_path(item)
        for item in raw.split(os.pathsep)
        if item.strip()
    }
    return frozenset(root for root in roots if not is_denied_project_root(root))


def safe_project_roots() -> frozenset[Path]:
    return SAFE_PROJECT_ROOTS | additional_safe_project_roots()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def is_denied_project_root(path: Path) -> bool:
    return path in DENIED_PROJECT_ROOTS


def safe_workspace_project_root(path: Path) -> bool:
    return any(is_relative_to(path, root) for root in safe_project_roots()) and not is_denied_project_root(path)


def normalize_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def normalize_codex_alias(name: str) -> str:
    alias = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip()).strip("_").lower()
    return alias or "contextforge_service"


def project_root_hash(root: Path, uid: int | None = None) -> str:
    uid_value = os.getuid() if uid is None else uid
    return hashlib.sha256(f"{uid_value}:{root}".encode("utf-8")).hexdigest()


def project_identity(root: str | Path) -> ProjectIdentity:
    canonical_root = canonical_path(root)
    root_hash = project_root_hash(canonical_root)
    short_hash = root_hash[:12]
    slug = normalize_slug(canonical_root.name)
    server_slug = slug.replace("-", "_")
    instance_slug = f"serena-{slug}-{short_hash}"
    server_name = f"serena_{server_slug}_{short_hash}_server"
    return ProjectIdentity(
        root=canonical_root,
        slug=slug,
        hash=short_hash,
        instance_slug=instance_slug,
        server_name=server_name,
        root_hash=root_hash,
    )


def stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


CLIENT_RELOAD_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "codex": {
        "client_type": "codex",
        "required_after": ["project_activation_apply"],
        "command": "start_new_session",
        "actor": "user",
        "instruction": (
            "After approved Codex project-local MCP config changes, start a new Codex session from the project root before relying on the newly installed tools. "
            "Codex launches configured MCP servers and exposes their tools when a session starts; /mcp is a status view and does not reload MCP tools in-place."
        ),
        "blocks_validation_until_done": True,
    },
    "pi": {
        "client_type": "pi",
        "required_after": ["global_extension_install_or_upgrade", "project_activation_apply"],
        "command": "/reload",
        "actor": "pi_agent",
        "instruction": "After an approved user-global Pi extension install or upgrade, issue /reload in Pi so the new or changed extension tools are active.",
        "blocks_validation_until_done": True,
    },
    "gemini": {
        "client_type": "gemini",
        "required_after": ["project_activation_apply"],
        "command": "start_new_session",
        "actor": "user",
        "instruction": (
            "After approved Gemini project-local MCP settings changes, start a new Gemini CLI session from the project root before relying on the newly installed tools. "
            "Gemini CLI discovers configured MCP servers when a session starts."
        ),
        "blocks_validation_until_done": True,
    },
    "opencode": {
        "client_type": "opencode",
        "required_after": ["project_activation_apply"],
        "command": "start_new_session",
        "actor": "user",
        "instruction": (
            "After approved OpenCode project-local MCP config changes, start a new OpenCode session from the project root before relying on the newly installed tools. "
            "OpenCode discovers project-local MCP servers and loads the user-home ContextForge plugin when a session starts."
        ),
        "blocks_validation_until_done": True,
    }
}


def client_reload_requirement(client_type: str, *, event: str) -> dict[str, Any] | None:
    requirement = CLIENT_RELOAD_REQUIREMENTS.get(client_type)
    if not requirement or event not in set(requirement.get("required_after") or []):
        return None
    return json.loads(json.dumps(requirement))


def load_server_instance_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"server instance manifest must be a JSON object: {manifest_path}")
    return data


def iter_server_instance_manifests(server_instances_root: str | Path = SERVER_INSTANCES_ROOT) -> Iterable[tuple[Path, dict[str, Any]]]:
    root = Path(server_instances_root)
    for manifest_path in sorted(root.glob("*/instance.json")):
        try:
            yield manifest_path, load_server_instance_manifest(manifest_path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue


def discover_contextforge_hosted_services(
    *,
    project_root: str | Path | None = None,
    contextforge_servers: Iterable[dict[str, Any]] | None = None,
    server_instances_root: str | Path = SERVER_INSTANCES_ROOT,
) -> list[dict[str, Any]]:
    """Return service activation candidates from manifests plus optional live readback.

    ContextForge live readback is the authority for whether a virtual server is
    currently visible. Manifests provide the backend home, scope metadata, and
    safe client alias. Missing live readback does not invent identity; it marks
    the candidate as not checked so project-init can ask the assistant to probe
    before applying.
    """

    canonical_project = canonical_path(project_root) if project_root is not None else None
    readback_by_name = {
        str(server.get("name")): server
        for server in (contextforge_servers or [])
        if isinstance(server, dict) and server.get("name")
    }
    services: list[dict[str, Any]] = []
    for manifest_path, manifest in iter_server_instance_manifests(server_instances_root):
        if manifest.get("enabled") is False:
            continue
        virtual_server = _manifest_virtual_server(manifest)
        server_name = str(virtual_server.get("name") or manifest.get("server_name") or "")
        if not server_name:
            continue
        service_family = str(manifest.get("service") or manifest.get("slug") or manifest.get("name") or manifest_path.parent.name)
        canonical_project_root = manifest.get("canonical_project_root")
        if canonical_project_root and canonical_project is not None:
            if canonical_path(str(canonical_project_root)) != canonical_project:
                continue
        instantiation_class = _manifest_instantiation_class(manifest)
        alias = normalize_codex_alias(str(manifest.get("codex_alias") or service_family))
        live_server = readback_by_name.get(server_name)
        registration = manifest.get("registration") if isinstance(manifest.get("registration"), dict) else {}
        manifest_provisioning_required = _serena_manifest_needs_project_provisioning(manifest)
        status = (
            "not_provisioned"
            if manifest_provisioning_required
            else ("matched" if live_server else ("not_checked" if contextforge_servers is None else "missing"))
        )
        provisioning_required = manifest_provisioning_required or status in {"missing", "stale"}
        scope = manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {}
        if provisioning_required and not scope and canonical_project_root:
            scope = _serena_project_scope(canonical_path(str(canonical_project_root)), provisioned=False)
        bridge = manifest.get("bridge") if isinstance(manifest.get("bridge"), dict) else {}
        if provisioning_required and not bridge:
            bridge = _serena_project_bridge(provisioned=False)
        descriptor = _redacted_manifest_descriptor(manifest, server_name, instantiation_class)
        if scope:
            descriptor["scope"] = scope
        descriptor["provisioning_status"] = "required" if provisioning_required else "manifest_backed"
        services.append(
            {
                "service_family": service_family,
                "canonical_service": str(manifest.get("canonical_service") or service_family),
                "service_binding": _manifest_service_binding(service_family, instantiation_class, canonical_project_root),
                "codex_alias": alias,
                "instantiation_class": instantiation_class,
                "backend_instance": str(manifest_path.parent.relative_to(REPO_ROOT)),
                "manifest_path": str(manifest_path.relative_to(REPO_ROOT)),
                "virtual_server": server_name,
                "gateway": _manifest_gateway_name(manifest),
                "contextforge_readback_status": status,
                "contextforge_server_id": str(live_server.get("id")) if live_server and live_server.get("id") else None,
                "registered_tools": list(registration.get("registered_tools") or []),
                "scope": scope,
                "bridge": bridge,
                "non_actions": _activation_non_actions(instantiation_class),
                "validation_policy": safe_validation_policy(service_family),
                "descriptor_digest": stable_digest(descriptor),
                **(
                    {
                        "provisioning": {
                            "status": "required",
                            "helper": "manage_serena_project_instance.py",
                            "requires_language_input": True,
                            "reason": "existing Serena manifest is missing ContextForge gateway or virtual-server registration",
                        }
                    }
                    if provisioning_required
                    else {}
                ),
            }
        )
    if canonical_project is not None and safe_workspace_project_root(canonical_project) and not _has_project_serena_service(services):
        services.append(_synthetic_serena_project_service(canonical_project))
    return services


def _has_project_serena_service(services: Iterable[dict[str, Any]]) -> bool:
    for service in services:
        if str(service.get("service_family") or "").lower() == "serena":
            return True
    return False


def _serena_manifest_needs_project_provisioning(manifest: dict[str, Any]) -> bool:
    if manifest.get("service") != "serena" and not str(manifest.get("name") or "").startswith("serena-"):
        return False
    contextforge = manifest.get("contextforge") if isinstance(manifest.get("contextforge"), dict) else {}
    gateway = contextforge.get("gateway") if isinstance(contextforge.get("gateway"), dict) else {}
    virtual = contextforge.get("virtual_server") if isinstance(contextforge.get("virtual_server"), dict) else {}
    return not (gateway.get("id") and virtual.get("id"))


def _serena_project_scope(project_root: Path, *, provisioned: bool) -> dict[str, Any]:
    state = "is configured" if provisioned else "will be started"
    note = (
        "Serena is stateful and project-scoped."
        if provisioned
        else "Serena is stateful and project-scoped. This project does not yet have a fully provisioned ContextForge Serena backend."
    )
    return {
        "configuration_signal": f"Serena {state} with --project {project_root}",
        "notes": note,
        "requires_local_project_scope": True,
        "scope_type": "single_workspace_code_intelligence",
        "workspace_root": str(project_root),
    }


def _serena_project_bridge(*, provisioned: bool) -> dict[str, Any]:
    return {
        "needed": False,
        "provider": None,
        "reason": "Serena exposes native streamable HTTP; no ContextForge bridge is used."
        if provisioned
        else "Serena exposes native streamable HTTP after approved project-scoped provisioning; no ContextForge bridge is used.",
        "streamable_http_url": None,
        "sse_url": None,
    }


def _synthetic_serena_project_service(project_root: Path) -> dict[str, Any]:
    identity = project_identity(project_root)
    scope = _serena_project_scope(identity.root, provisioned=False)
    bridge = _serena_project_bridge(provisioned=False)
    descriptor_source = {
        "name": identity.instance_slug,
        "slug": identity.instance_slug,
        "service": "serena",
        "instantiation_class": "instance_per_project",
        "virtual_server": identity.server_name,
        "scope": scope,
        "backend_transport": "streamable_http",
        "provisioning_status": "not_provisioned",
    }
    return {
        "service_family": "serena",
        "canonical_service": "serena",
        "service_binding": f"serena:{identity.hash}",
        "codex_alias": "serena",
        "instantiation_class": "instance_per_project",
        "backend_instance": f"server-instances/{identity.instance_slug}",
        "manifest_path": f"server-instances/{identity.instance_slug}/instance.json",
        "virtual_server": identity.server_name,
        "gateway": identity.instance_slug,
        "contextforge_readback_status": "not_provisioned",
        "contextforge_server_id": None,
        "registered_tools": [],
        "scope": scope,
        "bridge": bridge,
        "non_actions": _activation_non_actions("instance_per_project"),
        "validation_policy": safe_validation_policy("serena"),
        "descriptor_digest": stable_digest(descriptor_source),
        "provisioning": {
            "status": "required",
            "helper": "manage_serena_project_instance.py",
            "requires_language_input": True,
        },
    }


def safe_validation_policy(service_family: str) -> dict[str, Any]:
    normalized = normalize_codex_alias(service_family)
    policies: dict[str, dict[str, Any]] = {
        "context7": {
            "mode": "safe_call",
            "description": "list tools and call a non-mutating docs lookup or library-id resolution",
            "safe_operations": ["resolve-library-id", "query-docs"],
            "probe_contract": {
                "status": "known_safe_probe",
                "target_client_proof_layers": ["list_tools", "call_tool"],
                "allowed_tool_name_patterns": [
                    "context7-local-resolve-library-id",
                    "context7-local-query-docs",
                ],
                "default_probe": {
                    "safe_probe_id": "resolve-library-id",
                    "tool_name_hint": "context7-local-resolve-library-id",
                    "arguments": {
                        "libraryName": "python",
                        "query": "standard library documentation lookup",
                    },
                    "expected_result": "non-error library resolution result or explicit no-match response",
                },
                "accepted_proof_kinds": [
                    "target_client_safe_probe_result",
                    "pi_safe_probe_result",
                ],
                "validation_result_shape": {
                    "status": "passed",
                    "target_client_visible": True,
                    "proof_kind": "target_client_safe_probe_result",
                    "safe_probe_result": "passed",
                    "safe_probe_id": "resolve-library-id",
                    "verification_trace_refs": [
                        "contextforge://control-plane/traces/context7-target-client"
                    ],
                },
                "forbidden_substitutions": [
                    "backend health",
                    "direct bridge call",
                    "local package lookup",
                    "built-in web search",
                    "direct Upstash or Context7 backend call",
                ],
            },
            "requires_mutation_approval": False,
        },
        "mentality": {
            "mode": "read_only",
            "description": "list or read governance entries only",
            "safe_operations": ["governance-list", "governance-read"],
            "probe_contract": {
                "status": "known_safe_probe",
                "target_client_proof_layers": ["list_tools", "call_tool"],
                "allowed_tool_name_patterns": [
                    "mentality-governance-list",
                    "mentality-governance-read",
                    "governance_list",
                    "governance_read",
                ],
                "default_probe": {
                    "safe_probe_id": "governance-list",
                    "tool_name_hint": "mentality-governance-list",
                    "arguments": {"repo": "PROJECT_ROOT", "ledger": "decisions"},
                    "expected_result": "non-error governance entry listing with no ledger mutation",
                },
                "accepted_proof_kinds": [
                    "target_client_safe_probe_result",
                    "pi_safe_probe_result",
                ],
                "validation_result_shape": {
                    "status": "passed",
                    "target_client_visible": True,
                    "proof_kind": "target_client_safe_probe_result",
                    "safe_probe_result": "passed",
                    "safe_probe_id": "governance-list",
                    "verification_trace_refs": [
                        "contextforge://control-plane/traces/mentality-target-client"
                    ],
                },
                "forbidden_substitutions": [
                    "governance create",
                    "governance update",
                    "governance delete",
                    "local ledger file read",
                    "backend health",
                    "direct registry or bridge check",
                ],
            },
            "requires_mutation_approval": False,
        },
        "ssh_tmux": {
            "mode": "read_only",
            "description": "list sessions or read existing session visibility only",
            "safe_operations": ["list-sessions", "get-snapshot"],
            "probe_contract": {
                "status": "known_safe_probe",
                "target_client_proof_layers": ["list_tools", "call_tool"],
                "allowed_tool_name_patterns": [
                    "ssh-tmux-list-sessions",
                    "ssh-tmux-get-snapshot",
                    "list_sessions",
                    "get_snapshot",
                ],
                "default_probe": {
                    "safe_probe_id": "list-sessions",
                    "tool_name_hint": "ssh-tmux-list-sessions",
                    "arguments": {},
                    "expected_result": "non-error listing or empty listing of existing sessions without opening or mutating sessions",
                },
                "accepted_proof_kinds": [
                    "target_client_safe_probe_result",
                    "pi_safe_probe_result",
                ],
                "validation_result_shape": {
                    "status": "passed",
                    "target_client_visible": True,
                    "proof_kind": "target_client_safe_probe_result",
                    "safe_probe_result": "passed",
                    "safe_probe_id": "list-sessions",
                    "verification_trace_refs": [
                        "contextforge://control-plane/traces/ssh-tmux-target-client"
                    ],
                },
                "forbidden_substitutions": [
                    "open session",
                    "send command",
                    "send keys",
                    "cleanup dead sessions",
                    "close session",
                    "remote file read",
                    "remote file write",
                    "direct shell or tmux command",
                    "backend health",
                    "local process inspection",
                ],
            },
            "requires_mutation_approval": True,
            "mutation_boundary": "opening sessions or sending commands requires explicit approval",
        },
        "github": {
            "mode": "read_only_if_credentials_available",
            "description": "use list/search/read probes only where credentials allow",
            "safe_operations": ["search-repositories", "list-issues", "get-file-contents"],
            "requires_mutation_approval": False,
        },
        "web_search": {
            "mode": "safe_call",
            "description": "use search or fetch-like read probes only",
            "safe_operations": ["web-search", "fetch-content"],
            "requires_mutation_approval": False,
        },
        "exa_search": {
            "mode": "safe_call",
            "description": "use search or fetch-like read probes only",
            "safe_operations": ["web-search-exa", "web-fetch-exa"],
            "requires_mutation_approval": False,
        },
        "playwright": {
            "mode": "read_only_if_semantics_allow",
            "description": "list tools or inspect an inert page only; navigation/action probes may be skipped",
            "safe_operations": ["list-tools", "browser-snapshot"],
            "requires_mutation_approval": False,
        },
        "openzeppelin_solidity_contracts": {
            "mode": "safe_call",
            "description": "use documentation/template lookup or generation preview only when non-mutating",
            "safe_operations": ["solidity-erc20-preview"],
            "probe_contract": {
                "status": "known_safe_probe",
                "target_client_proof_layers": ["list_tools", "call_tool"],
                "allowed_tool_name_patterns": [
                    "openzeppelin-solidity-contracts-solidity-erc20",
                ],
                "default_probe": {
                    "safe_probe_id": "solidity-erc20-preview",
                    "tool_name_hint": "openzeppelin-solidity-contracts-solidity-erc20",
                    "arguments": {
                        "name": "ContextForgePreviewToken",
                        "symbol": "CFP",
                        "premint": "0",
                        "mintable": False,
                        "burnable": False,
                        "pausable": False,
                        "permit": False,
                        "callback": False,
                        "votes": False,
                        "flashmint": False,
                        "crossChainBridging": False,
                        "access": "none",
                        "upgradeable": False,
                    },
                    "expected_result": "deterministic Solidity preview text without deployment, file writes, secrets, wallet, chain, or RPC interaction",
                },
                "accepted_proof_kinds": [
                    "target_client_safe_probe_result",
                    "pi_safe_probe_result",
                ],
                "validation_result_shape": {
                    "status": "passed",
                    "target_client_visible": True,
                    "proof_kind": "target_client_safe_probe_result",
                    "safe_probe_result": "passed",
                    "safe_probe_id": "solidity-erc20-preview",
                    "verification_trace_refs": [
                        "contextforge://control-plane/traces/openzeppelin-target-client"
                    ],
                },
                "forbidden_substitutions": [
                    "remote availability",
                    "package documentation lookup",
                    "direct backend call",
                    "generated code audit claim",
                    "deployment approval",
                    "file write",
                    "project mutation",
                    "wallet or private key",
                    "chain or RPC interaction",
                    "secret-bearing input",
                ],
            },
            "requires_mutation_approval": False,
        },
    }
    return policies.get(
        normalized,
        {
            "mode": "skip_without_service_policy",
            "description": "validation skipped until a service-specific non-destructive probe is defined",
            "safe_operations": [],
            "requires_mutation_approval": False,
        },
    )


def safe_probe_contract(service_family: str) -> dict[str, Any]:
    policy = safe_validation_policy(service_family)
    contract = policy.get("probe_contract")
    return dict(contract) if isinstance(contract, dict) else {}


def build_safe_probe_validation_result(
    service_family: str,
    *,
    target_client: str,
    tool_name: str | None,
    verification_trace_refs: Iterable[str] | None,
    proof_kind: str = "target_client_safe_probe_result",
    safe_probe_id: str | None = None,
    safe_probe_result: str = "passed",
    status: str = "passed",
    result_summary: str | None = None,
) -> dict[str, Any]:
    """Shape already-observed safe probe proof into project-init result JSON.

    This helper does not call ContextForge or any target client. It only accepts
    metadata from a caller that already observed target-client-visible proof.
    """
    contract = safe_probe_contract(service_family)
    trace_refs = [str(ref) for ref in (verification_trace_refs or []) if str(ref)]
    selected_probe_id = safe_probe_id or str((contract.get("default_probe") or {}).get("safe_probe_id") or "")
    result = {
        "status": "pending",
        "target_client_visible": False,
        "proof_kind": proof_kind,
        "safe_probe_result": safe_probe_result,
        "safe_probe_id": selected_probe_id,
        "target_client": target_client,
        "tool_name": tool_name,
        "verification_trace_refs": trace_refs,
    }
    if result_summary:
        result["result_summary"] = result_summary

    if not contract:
        result["skipped_reason"] = "no_safe_probe_contract"
        return result

    accepted_proof_kinds = {str(item) for item in contract.get("accepted_proof_kinds") or []}
    if proof_kind not in accepted_proof_kinds:
        result["skipped_reason"] = "unsupported_proof_kind"
        return result

    allowed_tools = [str(item) for item in contract.get("allowed_tool_name_patterns") or []]
    if not tool_name or not any(pattern and pattern in tool_name for pattern in allowed_tools):
        result["skipped_reason"] = "no_matching_safe_tool"
        return result

    policy_operations = {str(item) for item in safe_validation_policy(service_family).get("safe_operations") or []}
    if selected_probe_id not in policy_operations:
        result["skipped_reason"] = "unsupported_safe_probe_id"
        return result

    if not trace_refs:
        result["skipped_reason"] = "missing_target_client_trace"
        return result

    if status not in {"passed", "verified"} or safe_probe_result != "passed":
        result["skipped_reason"] = "safe_probe_not_passed"
        return result

    result["status"] = "passed"
    result["target_client_visible"] = True
    result.pop("skipped_reason", None)
    return result


def validate_project_root(root: str | Path, *, require_workspace: bool = False) -> Path:
    canonical_root = canonical_path(root)
    if is_denied_project_root(canonical_root):
        raise ValueError(f"refusing denied project root: {canonical_root}")
    if canonical_root == Path("/").resolve():
        raise ValueError("refusing filesystem root as project root")
    if require_workspace and not safe_workspace_project_root(canonical_root):
        raise ValueError(f"project root is not under a safe project root: {canonical_root}")
    if canonical_root == HOME or is_relative_to(HOME, canonical_root):
        raise ValueError(f"refusing user home or parent of user home as project root: {canonical_root}")
    return canonical_root


def _git_root(cwd: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return canonical_path(root) if root else None


def _marker_root(cwd: Path) -> Path | None:
    for candidate in (cwd, *cwd.parents):
        if candidate in DENIED_PROJECT_ROOTS:
            return None
        if any((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    return None


def _empty_workspace_dir_root(cwd: Path) -> Path | None:
    if not safe_workspace_project_root(cwd):
        return None
    if not cwd.is_dir():
        return None
    try:
        next(cwd.iterdir())
    except StopIteration:
        return cwd
    except OSError:
        return None
    return None


def _explicit_safe_root(cwd: Path) -> Path | None:
    if not safe_workspace_project_root(cwd):
        return None
    for root in sorted(additional_safe_project_roots(), key=lambda path: len(path.parts), reverse=True):
        if cwd == root or is_relative_to(cwd, root):
            return root
    return None


def _workspace_child_root(cwd: Path) -> Path | None:
    if not is_relative_to(cwd, WORKSPACE_ROOT) or cwd == WORKSPACE_ROOT:
        return None
    relative = cwd.relative_to(WORKSPACE_ROOT)
    if not relative.parts:
        return None
    return WORKSPACE_ROOT / relative.parts[0]


def detect_project_root(cwd: str | Path) -> Path | None:
    """Resolve a canonical project root without ever returning home/root/workspace."""

    canonical_cwd = canonical_path(cwd)
    candidates = []
    git_root = _git_root(canonical_cwd)
    if git_root is not None:
        candidates.append(git_root)
    explicit_safe_root = _explicit_safe_root(canonical_cwd)
    if explicit_safe_root is not None:
        candidates.append(explicit_safe_root)
    empty_workspace_dir = _empty_workspace_dir_root(canonical_cwd)
    if empty_workspace_dir is not None:
        candidates.append(empty_workspace_dir)
    marker_root = _marker_root(canonical_cwd)
    if marker_root is not None:
        candidates.append(marker_root)
    workspace_child = _workspace_child_root(canonical_cwd)
    if workspace_child is not None:
        candidates.append(workspace_child)

    for candidate in candidates:
        canonical_candidate = canonical_path(candidate)
        if is_denied_project_root(canonical_candidate):
            continue
        if canonical_candidate == Path("/").resolve():
            continue
        if canonical_candidate == HOME:
            continue
        return canonical_candidate
    return None


def read_project_env(project_root: str | Path) -> dict[str, str]:
    env_path = canonical_path(project_root) / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in PROJECT_ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _manifest_virtual_server(manifest: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get(ENV_USE_DEV_DOCKER_VIRTUAL_SERVER) in {"1", "true", "yes"}:
        dev_docker = manifest.get("dev_docker") if isinstance(manifest.get("dev_docker"), dict) else {}
        dev_contextforge = dev_docker.get("contextforge") if isinstance(dev_docker.get("contextforge"), dict) else {}
        dev_name = str(dev_contextforge.get("virtual_server_name") or "")
        if dev_name:
            return {"name": dev_name}
    contextforge = manifest.get("contextforge") if isinstance(manifest.get("contextforge"), dict) else {}
    virtual = contextforge.get("virtual_server") if isinstance(contextforge.get("virtual_server"), dict) else {}
    return virtual


def _manifest_gateway_name(manifest: dict[str, Any]) -> str | None:
    contextforge = manifest.get("contextforge") if isinstance(manifest.get("contextforge"), dict) else {}
    gateway = contextforge.get("gateway") if isinstance(contextforge.get("gateway"), dict) else {}
    name = gateway.get("name")
    return str(name) if name else None


def _manifest_instantiation_class(manifest: dict[str, Any]) -> str:
    if manifest.get("service") == "serena" or str(manifest.get("name") or "").startswith("serena-"):
        return "instance_per_project"
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {}
    scope_type = str(scope.get("scope_type") or "")
    if manifest.get("slug") == "mentality" or scope_type == "caller_supplied_local_repo":
        return "static_repo_local"
    if scope_type in {"ssh_target_and_tmux_session", "isolated_browser_runtime"}:
        return "session_scoped"
    if "credential" in scope_type:
        return "credential_scoped"
    if "resource" in scope_type:
        return "resource_scoped"
    if scope.get("requires_local_project_scope") is True:
        return "instance_per_project"
    return "shared_canonical"


def _manifest_service_binding(service_family: str, instantiation_class: str, canonical_project_root: Any) -> str:
    if instantiation_class == "instance_per_project" and canonical_project_root:
        return f"{service_family}:{project_root_hash(canonical_path(str(canonical_project_root)))[:12]}"
    if instantiation_class == "shared_canonical":
        return f"{service_family}:canonical"
    return f"{service_family}:{instantiation_class}"


def _activation_non_actions(instantiation_class: str) -> list[str]:
    actions = [
        "do not mutate user-global Codex config or trust",
        "do not write secrets or token material",
        "do not mutate the live ContextForge registry or catalog",
    ]
    if instantiation_class == "shared_canonical":
        actions.extend(
            [
                "do not create a per-project backend",
                "do not create a per-project gateway, bridge, wrapper, port, unit, or server-instance directory",
            ]
        )
    elif instantiation_class != "instance_per_project":
        actions.append("do not duplicate the backend for client alias or project-name convenience")
    return actions


def _redacted_manifest_descriptor(manifest: dict[str, Any], server_name: str, instantiation_class: str) -> dict[str, Any]:
    return {
        "name": manifest.get("name"),
        "slug": manifest.get("slug"),
        "service": manifest.get("service"),
        "instantiation_class": instantiation_class,
        "virtual_server": server_name,
        "scope": manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {},
        "backend_transport": (manifest.get("backend") or {}).get("transport") if isinstance(manifest.get("backend"), dict) else None,
    }


def write_project_env(project_root: str | Path, updates: dict[str, str]) -> None:
    unknown = set(updates) - PROJECT_ENV_KEYS
    if unknown:
        raise ValueError(f"refusing non-whitelisted .env keys: {sorted(unknown)}")

    root = canonical_path(project_root)
    env_path = root / ".env"
    existing = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    remaining = dict(updates)
    output: list[str] = []

    for raw_line in existing:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(raw_line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(raw_line)

    for key in sorted(remaining):
        output.append(f"{key}={remaining[key]}")

    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
