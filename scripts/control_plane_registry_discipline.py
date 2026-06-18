#!/usr/bin/env python3
"""ContextForge registry mutation discipline helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA_URI = "contextforge://control-plane/registry-mutation-discipline/v1"
PUBLIC_API_MUTATION_PATH = "public_contextforge_api_or_admin_ui_after_explicit_approval"
FORBIDDEN_MUTATION_SURFACES = [
    "direct_contextforge_database_write",
    "contextforge_internal_patch",
    "stored_id_authority_without_canonical_name_readback",
]
CANONICAL_AUTHORITY_FIELDS = [
    "gateway.name",
    "gateway.url",
    "server.name",
    "prompt.name",
    "resource.uri",
    "tool.name",
    "backend_manifest.scope",
]

ALLOWED_CONTEXTFORGE_API_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GET", re.compile(r"^/gateways(?:\?.*)?$")),
    ("POST", re.compile(r"^/gateways$")),
    ("PUT", re.compile(r"^/gateways/[^/?]+$")),
    ("POST", re.compile(r"^/gateways/[^/?]+/tools/refresh$")),
    ("GET", re.compile(r"^/tools(?:\?.*)?$")),
    ("GET", re.compile(r"^/servers(?:\?.*)?$")),
    ("POST", re.compile(r"^/servers$")),
    ("PUT", re.compile(r"^/servers/[^/?]+$")),
    ("GET", re.compile(r"^/resources(?:\?.*)?$")),
    ("POST", re.compile(r"^/resources$")),
    ("PUT", re.compile(r"^/resources/[^/?]+$")),
    ("GET", re.compile(r"^/prompts(?:\?.*)?$")),
    ("POST", re.compile(r"^/prompts$")),
    ("PUT", re.compile(r"^/prompts/[^/?]+$")),
)


class RegistryMutationDisciplineError(ValueError):
    """Raised when a registry operation leaves the approved ContextForge API surface."""


def assert_public_contextforge_api_path(method: str, path: str) -> None:
    """Validate that a registry helper is calling a public ContextForge API path."""

    normalized_method = str(method).strip().upper()
    normalized_path = str(path).strip()
    if not normalized_path.startswith("/"):
        raise RegistryMutationDisciplineError(f"ContextForge API path must be absolute: {path}")
    for allowed_method, allowed_pattern in ALLOWED_CONTEXTFORGE_API_PATTERNS:
        if normalized_method == allowed_method and allowed_pattern.match(normalized_path):
            return
    raise RegistryMutationDisciplineError(f"unsupported ContextForge registry API operation: {method} {path}")


def registry_mutation_discipline(*, owner: str, operations: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """Return the issue #140 registry mutation discipline record for a helper surface."""

    return {
        "schema_uri": SCHEMA_URI,
        "issue": "#140",
        "owner": str(owner),
        "mutation_path": PUBLIC_API_MUTATION_PATH,
        "direct_database_writes_allowed": False,
        "contextforge_internal_patches_allowed": False,
        "stored_ids_are_authority": False,
        "stored_id_use": "transport references only after canonical name/url/uri readback",
        "canonical_authority_fields": list(CANONICAL_AUTHORITY_FIELDS),
        "allowed_contextforge_api_operations": [
            {"method": method, "path_pattern": pattern.pattern}
            for method, pattern in ALLOWED_CONTEXTFORGE_API_PATTERNS
        ],
        "forbidden_mutation_surfaces": list(FORBIDDEN_MUTATION_SURFACES),
        "operations": [dict(operation) for operation in operations],
    }
