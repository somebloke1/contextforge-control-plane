# ContextForge Service Locality Policy

This harness keeps the IBM ContextForge gateway container stock unless a
specific MCP backend proves that it must run inside the gateway container.

## Default Shape

- `contextforge-gateway`: stock IBM ContextForge gateway only.
- MCP backends: run where their real locality belongs: another container, the
  host, a client machine, a Pi, or another reachable host.
- ContextForge registration: points at packetized MCP endpoints exposed by the
  backend or by a transceiver next to the backend.
- Transport contract: expose both SSE (`/sse`) and streamable HTTP (`/mcp`) for
  every MCP service when both transports validate as working.

Do not install MCP server files, client-local tools, or host project trees into
the gateway container by default.

## Stdio Backends

Stdio is process-local. A stdio MCP backend can live on any reachable machine,
but its stdio transceiver must run beside it.

```text
ContextForge gateway
  -> HTTP/SSE over the network
  -> transceiver on the backend host
  -> local stdio MCP process
```

Use the ContextForge-provided bridge process as that transceiver:

```sh
python -m mcpgateway.translate \
  --stdio "actual-mcp-command" \
  --host 0.0.0.0 \
  --port 9201 \
  --expose-sse \
  --expose-streamable-http
```

The gateway registers the transceiver's validated `/sse` and `/mcp` endpoints.
It does not reach directly into the backend host's filesystem or process table.

## Native Packetized Backends

When a backend already exposes SSE and streamable HTTP, register both validated
endpoints directly. When it exposes only one transport, register that native
endpoint and bridge only the missing transport:

```sh
python -m mcpgateway.translate \
  --connect-sse http://backend:9201/sse \
  --host 0.0.0.0 \
  --port 9202 \
  --expose-streamable-http
```

```sh
python -m mcpgateway.translate \
  --connect-streamable-http http://backend:9201/mcp \
  --host 0.0.0.0 \
  --port 9203 \
  --expose-sse
```

## Container Choices

Prefer one backend container per meaningful locality boundary:

- distinct dependency stack;
- distinct credential scope;
- distinct filesystem or hardware access;
- distinct lifecycle or health check;
- distinct operator approval boundary.

A shared backend container is acceptable only when those boundaries are
intentionally the same.

## Single-User Backends

Some MCP backends are functionally single-user even when they can expose a
packetized transport. Do not paper over that constraint with one shared backend.

When a backend is single-user, run one backend or transceiver instance per
credential, user, project, or client-local state boundary. Assign each instance
a unique reserved port in `9200-9299`, give it a distinct ContextForge
registration identity, and verify both `/sse` and `/mcp` for that instance when
the backend supports both transports.

## Gateway-Container Exception

Installing MCP backend files or services inside the ContextForge gateway
container is deferred until a concrete backend requires it. If that happens,
document:

- why a remote/container/host transceiver is insufficient;
- which files, credentials, and runtime dependencies enter the gateway image;
- how the change remains idempotent and reversible;
- how gateway upgrades remain stock or intentionally patched;
- how the service is tested without depending on unrelated host paths.

## First Integration Path

For the first service integration, use a backend-local transceiver before any
gateway-container MCP install:

1. choose one service with a clear backend home under `server-instances/`;
2. run its MCP process and any stdio transceiver outside the gateway container;
3. expose the transceiver on a unique port in the reserved `9200-9299` range;
4. verify `/health` or process health plus `/sse` and `/mcp` as applicable;
5. register all validated packetized endpoints with ContextForge through the
   API;
6. verify ContextForge readback and client access through the gateway.
