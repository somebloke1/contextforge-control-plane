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

## Project-Scoped MCP Container Matrix

Do not Dockerize every MCP backend by default. Choose a container shape from
the backend's real service boundary:

| Service class | Container default | Reason |
| --- | --- | --- |
| Shared canonical services such as `mentality`, `context7`, `playwright`, `ssh-tmux`, `exa-search`, `github`, `web-search`, and hosted/native services | Shared service or existing native endpoint | These services are not project-specific by default; duplicating them per project would create sibling identities, token scope drift, port churn, and extra lifecycle state without proving new behavior. |
| Credential-scoped or user-scoped services | One backend or transceiver per credential or user when the backend cannot safely multiplex | Credential and local-user boundaries are service boundaries. A shared container is acceptable only when the credential scope and lifecycle are intentionally shared. |
| Session-scoped or client-local services | One backend or transceiver per client-local state boundary only when required | Client config discovery is not service identity. Keep client-local state out of the gateway image and avoid per-client duplication unless runtime behavior materially differs. |
| Project-scoped services | One backend or transceiver per project when the backend reads or writes project-local state | The project filesystem, project metadata, code index, language server state, and approval boundary are part of the service identity. |
| Gateway-integrated services | Deferred exception | Installing MCP services into the gateway image requires a concrete backend that cannot be served by a backend-local container or host transceiver. |

`Serena` is the current clear `instance_per_project` service. It starts with a
single `--project` root, owns project-local code intelligence state, and should
have a canonical cf-controlplane instance such as
`server-instances/serena-cf-controlplane-d46fe58a2a20` unless a separate
GitHub-tracked compatibility decision explicitly keeps the legacy
`serena-cf-controlplane-d46fe58a2a20` identity with target-client-visible validation and
retirement conditions.

`project-inspector` is the next plausible non-Serena project-scoped proof
candidate, but only after an MCP backend and `server-instances/` manifest seed
exist. Until then, treat it as a design candidate, not an implied runtime
service.

Runtime Docker or service work for these project-scoped services is not a
documentation-only action. Creating containers, allocating ports, registering
ContextForge gateways, changing systemd units, writing runtime state, or
changing client config requires the explicit runtime approval boundary for that
surface.

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

For the first service integration, use the `mentality-transceiver` development
sidecar before any gateway-container MCP install. It runs the stock
ContextForge bridge against the repo-local governance MCP server:

```sh
docker compose -f docker/contextforge-harness/compose.yml up -d --build \
  contextforge-gateway mentality-transceiver
docker/contextforge-harness/scripts/probe-mentality-dev.py --direct-only
docker/contextforge-harness/scripts/register_mentality_dev.py
docker/contextforge-harness/scripts/probe-mentality-dev.py
```

The sidecar exposes host direct endpoints at `127.0.0.1:9201` and the gateway
registers the compose-network URL `http://mentality-transceiver:9201/mcp`.
The development harness env enables `SSRF_ALLOW_PRIVATE_NETWORKS=true` so the
stock gateway can register compose-network upstreams. Keep that setting scoped
to this isolated development surface. The virtual MCP probe uses a temporary
server-scoped catalog token instead of the admin session JWT, then revokes that
token after readback.

For additional service integrations, use a backend-local transceiver before any
gateway-container MCP install:

1. choose one service with a clear backend home under `server-instances/`;
2. run its MCP process and any stdio transceiver outside the gateway container;
3. expose the transceiver on a unique port in the reserved `9200-9299` range;
4. verify `/health` or process health plus `/sse` and `/mcp` as applicable;
5. register all validated packetized endpoints with ContextForge through the
   API;
6. verify ContextForge readback and client access through the gateway.

`exa-search` follows this pattern for the 4445 successor: the repo-local
Python backend runs in `exa-search-transceiver`, reads only the ignored
`server-instances/exa-search/.env`, and is registered by the gateway through
the compose-network URL `http://exa-search-transceiver:9205/mcp` only after
credential-env preflight and direct reachability evidence. Do not fall back to
the host-loopback `127.0.0.1:9105` live surface for Docker successor parity.
