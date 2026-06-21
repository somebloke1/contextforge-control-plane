# Agent Instructions

This repository builds and operates a clean, stock IBM ContextForge MCP Gateway
installation for ContextForge-style MCP aggregation.

## Current Goal

Work toward a systemd-controlled ContextForge installation that:

- Inventories MCP servers, extensions, and tool scripts configured for Codex
  Desktop/Terminal, Claude Desktop, Claude Code, Gemini CLI, and OpenCode on
  this host.
- Registers canonical MCP servers, REST/API tools, and hosted services through
  native ContextForge mechanisms. Client configs are discovery sources, not
  service identities.
- Provides HTTP and SSE access where required.
- Uses ContextForge/package-provided bridge or translation support only when a
  discovered service lacks required HTTP or SSE access.
- Preserves services that already expose suitable HTTP/SSE transports without
  wrapping them unnecessarily.
- Tests runtime behavior with real commands and endpoint probes.

## Git Policy

- `main` is protected by tracked hooks in `.githooks/`.
- `dev-root` is the root for agent-created branches.
- Create agent or feature work branches from `dev-root`.
- Do not commit directly to `main` except for explicit administrative bootstrap
  work with `ALLOW_MAIN_COMMIT=1`.
- Keep `core.hooksPath` set to `.githooks`.

## Python Environment

- Every branch/worktree must have its own local `.venv`; no branch is left
  without one. Create or repair it with `uv venv .venv` before branch-local
  validation when it is absent.
- The Python environment was created with `uv venv .venv`.
- Use `uv pip install --python .venv/bin/python ...` for dependency
  installation with the currently installed `uv`.
- If a valuable or integral local development/test enabler is missing and can
  be installed into the current worktree `.venv`, install it there and record
  the command/evidence. Do not rely on the user for ordinary local `.venv`
  package installation, and do not treat a missing installable package as a
  reason to skip validation.
- Do not assume `python -m pip` exists until verified.
- Keep `.venv/` out of Git.

## Secrets And Local State

- Do not commit real API keys, bearer tokens, passwords, generated JWTs, or
  client-local secret values.
- Keep runtime env files in ignored local paths such as
  `config/contextforge.env`, `server-instances/<name>/.env`, or installed
  `/etc/contextforge/*.env` files.
- Inventory outputs ending in `.local.json` are host-specific and ignored.
- Generated diagnostics and temporary assets under `generated/` are ignored by
  default unless intentionally promoted to tracked templates.

## Governance Ledgers

- Use `DECISIONS.md`, `ABEYANT_INTENTIONS.md`, and `OPEN_QUESTIONS.md` for
  durable project continuity.
- Preserve the `governance-crud` entry anchors and metadata shape adopted from
  `/home/dgk/workspace/mtga-builder`.
- Use `scripts/governance_crud.py` for repeatable ledger edits and
  `scripts/governance_mcp.py` for the repo-local MCP service named
  `mentality`.
- Keep `mentality` as a static repo-local stdio source, independent of external
  client configs.

## Implementation Notes

- Use `CONTEXTFORGE_SCHEMA.md` as the local ContextForge API schema and method
  reference before automating registry, token, team, or Admin/API operations.
- Change ContextForge-owned state through the ContextForge API or Admin UI
  behavior. Direct ContextForge database writes are prohibited; direct database
  reads are diagnostic only.
- Prefer stock ContextForge configuration and native registration over
  project-local duplicate gateway, translator, registration, or generated
  service fleet implementations.
- Deduplicate discovered services by actual backend package/server, runtime
  scope, credential scope, and exposed resource scope. Do not create separate
  services named after Codex, Claude, Gemini, or OpenCode merely because those
  client configs mentioned the same service.
- Every service exposed by ContextForge must have a concrete upstream backend
  home under `server-instances/<service-slug>/` or an explicitly documented
  equivalent. These directories are the operational source for backend MCP
  servers, package bridge commands, REST/OpenAPI definitions, health probes, and
  sanitized registration metadata.
- `server-instances/<service-slug>/` is not a replacement gateway fleet:
  ContextForge remains the stock registry/proxy, native HTTP/SSE services are
  registered directly, and bridges only expose missing transports.
- Prefer repeatable, thin operator scripts over one-off shell state when scripts
  call package-provided commands or APIs directly.
- Use `scripts/register_tool_guidance.py` to register or refresh tool-bound
  prompt/resource documentation. The script must use ContextForge APIs, preserve
  gateway-wide content-security validation, preflight generated content, and
  shape documentation text when stock validation would otherwise flag benign
  Markdown or prose.
- Inventory client configs read-only before registering or bridging services.
- Preserve native MCP transports where present.
- For stdio MCP servers, bridge with:
  `python -m mcpgateway.translate --stdio ... --expose-sse --expose-streamable-http`.
- For SSE-only servers, bridge only the missing HTTP side with
  `--connect-sse ... --expose-streamable-http`.
- For HTTP-only servers, bridge only the missing SSE side with
  `--connect-streamable-http ... --expose-sse`.
- User-level systemd activation is acceptable for local operation. System-level
  activation still requires root because this user cannot write
  `/etc/systemd/system`, `/opt`, or `/var/lib` without sudo.

## Verification

- Use current local files, command output, service state, and HTTP probes as
  authority.
- Verify the clean stock server before registering any external services.
- Before claiming completion, verify inventory coverage, gateway health, bridge
  health where bridges are needed, ContextForge registration, and exposed `/sse`
  plus `/mcp` endpoints.
- After root installation, verify installed unit files, service state, admin
  UI/API behavior, registry contents, and live endpoint probes against the
  systemd-controlled gateway.
