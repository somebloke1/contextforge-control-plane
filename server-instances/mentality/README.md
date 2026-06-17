# mentality

Backend home for the repo-local governance MCP service.

This service is implemented by `scripts/governance_mcp.py` as a stdio MCP
server. It needs package bridge support because stdio is not directly
registerable as an HTTP/SSE ContextForge gateway.

Runtime shape:

- Backend: `.venv/bin/python scripts/governance_mcp.py`
- Bridge: `python -m mcpgateway.translate`
- Direct bridge SSE: `http://127.0.0.1:9100/sse`
- Direct bridge streamable HTTP: `http://127.0.0.1:9100/mcp`
- ContextForge gateway name: `mentality`
- ContextForge virtual server name: `mentality_server`

Use `./run-bridge.sh` from the repository root to start the bridge.

Development Docker shape:

- Compose service: `mentality-transceiver`
- Bridge: `python -m mcpgateway.translate`
- Host direct streamable HTTP: `http://127.0.0.1:9201/mcp`
- Host direct SSE: `http://127.0.0.1:9201/sse`
- ContextForge dev gateway registration URL:
  `http://mentality-transceiver:9201/mcp`
- ContextForge dev gateway name: `mentality-dev-docker`
- ContextForge dev virtual server name: `mentality_dev_docker_server`

The Docker transceiver is for the isolated ContextForge development harness. Do
not register it into the legacy/live host ContextForge surface.
