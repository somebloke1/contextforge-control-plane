# Pi ContextForge Integration Architecture

Date: 2026-06-17

This note records the current Pi integration direction for the
ContextForge control-plane work. It is source-only readiness material: it does
not install or reload Pi, mutate user-global Pi files, copy secrets, change
ContextForge registry state, or touch the legacy/live ContextForge surface.

## Decision

Pi integration has three distinct layers. They should not be collapsed into one
mechanism.

1. **Pi user experience layer: global TypeScript extension shim.**
   Pi does not use a project-local MCP config surface equivalent to Codex
   `mcp_servers`. The canonical Pi-facing path is the repo-owned global
   TypeScript extension source in
   `pi-extensions/contextforge-global-shim/`. The shim registers Pi-native
   tools, reads approved project bindings from
   `.project/context_forge_state.json`, exposes project-init helper tools, and
   imports ContextForge virtual-server MCP tools into deterministic Pi tool
   names. Ordinary project activation must not generate a fake Pi MCP config.

2. **ContextForge control/readback layer: public ContextForge APIs where they
   are stable and useful.**
   Direct ContextForge API calls are appropriate for helper-owned planning,
   catalog/readback, token lifecycle, virtual-server metadata, and other
   control-plane operations when the endpoint is public and already documented
   in `CONTEXTFORGE_SCHEMA.md`. Direct API use is not, by itself, a Pi tool
   integration strategy because Pi still needs a TypeScript extension to
   register tools and guide the agent.

3. **MCP service transport layer: stock gateway/transceiver endpoints.**
   Stdio MCP backends cannot be reached over IP without a front end. For
   ContextForge development Docker and client-container validation, stdio MCP
   servers should be fronted by stock ContextForge package support such as
   `python -m mcpgateway.translate --stdio ... --expose-sse
   --expose-streamable-http`. ContextForge should register the resulting
   validated `/sse` and `/mcp` endpoints on the isolated development Docker
   surface, not reach into host stdio processes or legacy/live services.

## Current Repo Shape

- `pi-extensions/contextforge-global-shim/index.ts` is the Pi extension source.
  It currently uses a child stdio MCP client to launch
  `scripts/contextforge_mcp_wrapper.py` for each approved virtual server, then
  maps MCP `tools/list`, `prompts/list`, and `resources/list` into Pi-visible
  readback, guidance lookup, validation, and imported tools.
- `scripts/pi_contextforge_shim_dry_run.py` models the same source-level
  imported-tool readback and can classify a user-requested tool name without
  fabricating a Pi route. Its `--requested-tool` path reports whether a tool is
  imported, blocked by the default safe Pi policy, absent because no Pi tools
  were imported, or unknown/unimported, then points to readback, guidance
  lookup, or project-init capability discovery as the recovery path. This is
  the source/test contract for #228; it is not ordinary interactive Pi-session
  proof.
- `scripts/manage_pi_global_shim.py` owns status, plan, and explicitly
  confirmed install/upgrade for the user-global Pi extension. Its status and
  plan paths are non-mutating. The install path requires
  `I_APPROVE_USER_GLOBAL_PI_EXTENSION_WRITE` and must be followed by Pi
  `/reload` before validation.
- Issue #3 remains the approval-gated live Pi install/reload/readback track.
- Issue #41 and PRs #42, #43, and #44 own the isolated development Docker
  gateway/transceiver plus OpenCode and Pi client-container smoke path.
- The legacy/live ContextForge surface remains read-only. Mutable service
  registration and endpoint experiments belong on the ContextForge development
  Docker surface plus Pi/OpenCode client Docker surfaces.

## Path Selection

Use this selection rule when choosing the next implementation slice:

| Question | Preferred path | Rationale |
| --- | --- | --- |
| How does Pi see ContextForge tools? | Pi global TypeScript extension shim | Pi needs `registerTool()`-style native tool registration; it does not consume project-local MCP config. |
| How should helper/control-plane code inspect ContextForge state? | Public ContextForge APIs | API readback is stable evidence for registry, virtual-server, token, prompt, resource, and tool state when documented. |
| How should stdio MCP backends talk to ContextForge across Docker/IP? | `mcpgateway.translate` or equivalent stock package transceiver | Stdio needs an HTTP/SSE front end before ContextForge or client containers can reach it over IP. |
| Should Pi directly call undocumented internal MCP HTTP endpoints? | No by default | Internal routes are not the control-plane contract; prefer public virtual-server `/mcp` plus a real MCP client, or keep the existing wrapper path. |

The current default remains the TypeScript shim plus repo-local MCP wrapper for
Pi source readiness, with the Docker transceiver stack used for IP-to-IP
integration proof. A direct TypeScript MCP-over-HTTP client inside the Pi shim
is a possible future simplification only after it is proven against the
development Docker ContextForge surface and preserves tool policy, guidance,
readback, token handling, and reload semantics.

## Non-Actions

This architecture record does not authorize:

- writing `~/.pi/agent/extensions/` or any user-global Pi config;
- asking Pi to `/reload`;
- copying runtime secrets, OAuth state, bearer tokens, or trust state;
- mutating legacy/live ContextForge registry, services, processes, systemd, or
  databases;
- mutating `/home/dgk/workspace/legacy-controlplane-archive`;
- merging the all-ready PR queue without explicit merge-sequence approval.

## Evidence To Claim Progress

For source-only slices, acceptable evidence includes doc/test readback,
TypeScript checks for the extension source, Python unit tests for helper and
wrapper behavior, and Docker/client harness probes that explicitly identify the
surface exercised.

For live Pi readiness, source checks are insufficient. Claiming issue #3
complete requires approved install/upgrade of the user-global shim, Pi
`/reload`, and Pi-visible validation/readback from the actual Pi surface.
