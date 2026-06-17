# MCP Transceiver Images

Development-only MCP backend/transceiver images for the isolated ContextForge
container harness.

The first image fronts the repo-local `mentality` stdio MCP backend with the
stock ContextForge bridge:

```sh
python -m mcpgateway.translate \
  --stdio "python scripts/governance_mcp.py" \
  --expose-sse \
  --expose-streamable-http \
  --host 0.0.0.0 \
  --port 9201
```

It copies only sanitized repo governance ledgers and governance server source
into the image. It does not mount or mutate the host checkout by default.

Runtime endpoints:

- Host direct streamable HTTP: `http://127.0.0.1:9201/mcp`
- Compose-network streamable HTTP for ContextForge registration:
  `http://mentality-transceiver:9201/mcp`
- Host direct SSE: `http://127.0.0.1:9201/sse`

Register it only with the ContextForge development Docker gateway, not the
legacy/live host gateway.
