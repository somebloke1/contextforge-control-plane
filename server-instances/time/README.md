# time

Development-foil MCP backend for the ContextForge onboarding factory.

This instance uses the upstream Model Context Protocol Time server as a
stateless baseline service. The upstream package exposes a stdio MCP server, so
the planned local ContextForge surface uses the package-provided
`mcpgateway.translate` bridge on `127.0.0.1:9109`, exposing both `/mcp` and
`/sse`.

The Time service is a development foil for proving repeatable onboarding. It is
not evidence that the seven selected foils are a final canonical service set.

Planned safe target-client proof, after runtime registration and client reload:

- list target-client-visible tools;
- call `get_current_time` with an IANA timezone such as `UTC`;
- do not infer target-client readiness from this manifest, bridge health, or
  local package behavior alone.
