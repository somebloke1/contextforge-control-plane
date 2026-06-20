# Cross-Client Scoped Token Contract - 2026-06-20

## Context

Issue #294 was opened from OpenCode transcript evidence, but the underlying
contract is cross-client. Codex, Pi, OpenCode, Gemini, and future clients should
not each invent separate ContextForge MCP authentication semantics.

## Current Contract

Ordinary project-init bindings launch `scripts/contextforge_mcp_wrapper.py` for
selected ContextForge virtual servers. The client config may provide wrapper
configuration such as `CONTEXTFORGE_CONFIG_ENV`, `CONTEXTFORGE_BASE_URL`, and a
wrapper token-cache path, but it must not embed bearer-token material,
`MCP_AUTH`, or raw `Authorization` headers.

The wrapper is the shared auth boundary:

- it may read local ContextForge admin credentials from the configured env file;
- it resolves the target virtual server to a ContextForge server id;
- unless an explicit `CONTEXTFORGE_BEARER_TOKEN` is supplied by a controlled dev
  smoke path, it creates a short-lived scoped catalog token for the target
  server;
- it forwards MCP traffic with that scoped token;
- it revokes the scoped token when the wrapper exits;
- it logs token lifecycle metadata without logging the access token value.

Controlled dev smoke scripts may create explicit short-lived probe tokens and
pass them with `CONTEXTFORGE_BEARER_TOKEN` when the point of the test is direct
client/tool-call proof against a dev gateway. That is a test harness exception,
not ordinary project-init client config.

## Implications

- The shared token contract belongs in the wrapper and helper/binding tests, not
  in each client adapter as duplicated auth logic.
- Client adapters should be evaluated for whether they project the wrapper
  launch correctly, not for whether they know how to mint ContextForge tokens.
- Evidence and transcripts may include token ids, server ids, permissions, and
  lifecycle events, but must not include the one-time access token value.
- If an activated client cannot use a service, diagnosis should distinguish
  wrapper startup, env-file availability, scoped-token creation, token revocation
  failure, ContextForge transport failure, and target service failure.

## Current Implementation Evidence

- `scripts/contextforge_mcp_wrapper.py` creates scoped catalog tokens through
  `/tokens`, uses them for `/servers/{server_id}/mcp/`, and revokes them on
  wrapper exit.
- The wrapper now emits `contextforge_wrapper_scoped_token_created` with
  non-secret metadata only: `server_id`, `token_id`, and permissions.
- Tests assert token creation/revocation use the catalog API, creation logging
  omits access-token material, and ordinary project-init bindings do not embed
  `CONTEXTFORGE_BEARER_TOKEN`, `MCP_AUTH`, or `Authorization`.
