# github

Canonical GitHub MCP backend for ContextForge.

This instance uses `@modelcontextprotocol/server-github`, the same backend
discovered in the OpenCode global config. It is promoted as one canonical
service because the backend, credential scope, and exposed GitHub account scope
come from the local `gh` authenticated account rather than from OpenCode
itself.

The bridge obtains `GITHUB_PERSONAL_ACCESS_TOKEN` at runtime with
`gh auth token`; do not write that token to tracked files. The backend is a
stdio MCP server exposed through `mcpgateway.translate` on `127.0.0.1:9106`
with both `/sse` and `/mcp` transports.

ContextForge registration:

- Gateway: `github` (`35de0ef8f791449898317435f986d6dd`)
- Virtual server: `github_server` (`898d2179080744ffadd0add57494f197`)
- Tools/prompts/resources: 26 each
