# exa-search

Canonical local Exa MCP backend for ContextForge.

This service replaces the hosted Exa MCP endpoint with a local backend that
uses the Exa Search/Contents APIs and Gemini `generateContent` for
LM-processed search answers.

Runtime secrets live in ignored `server-instances/exa-search/.env`:

- `EXA_API_KEY`
- `GEMINI_API_KEY`

The backend is a stdio MCP server exposed through `mcpgateway.translate` on
`127.0.0.1:9105` with both `/sse` and `/mcp` transports.
