# context7

Canonical Context7 MCP backend for ContextForge.

This instance uses the configured `@upstash/context7-mcp` stdio backend through
the package-provided `mcpgateway.translate` bridge on `127.0.0.1:9103`, exposing
both `/mcp` and `/sse` for ContextForge and clients that require those
transports. Native HTTP mode was intentionally not used for this workstation
because the required Upstash Redis REST credentials were not present in the
discovered client configs.

The duplicated Context7 entries discovered in individual assistant configs are
discovery evidence only and are superseded by this canonical service.
