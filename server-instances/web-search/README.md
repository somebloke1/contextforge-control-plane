# web-search

Canonical local web_search MCP backend for ContextForge.

This service exposes the standalone MCP server from
`/home/dgk/workspace/web_search/dist/mcp-server.js`. It provides web search,
URL/content extraction, code search, public GitHub repository extraction, and
PDF extraction.

Runtime secrets can live in ignored `server-instances/web-search/.env`:

- `EXA_API_KEY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GITHUB_TOKEN`
- `PERPLEXITY_API_KEY`
- `WEB_ACCESS_ENABLE_GEMINI_WEB`

`WEB_ACCESS_ENABLE_GEMINI_WEB` defaults to `false` for MCP operation unless the
ignored env file opts in explicitly.

The backend is a stdio MCP server exposed through `mcpgateway.translate` on
`127.0.0.1:9107` with both `/sse` and `/mcp` transports.
