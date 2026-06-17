# ContextForge Container Harness

Isolated IBM ContextForge gateway harness for integration testing while the
host development gateway remains untouched.

This harness intentionally starts only the ContextForge gateway. It does not
register MCP services.

Service locality and the first MCP integration path are defined in
`SERVICE_LOCALITY.md`.

## Runtime

- Image: `ghcr.io/ibm/mcp-context-forge:v1.0.3`
- Host URL: `http://127.0.0.1:4445`
- LAN URL: `http://<reachable-host-ip>:4445` when the host firewall/network
  allows access
- Container URL: `http://127.0.0.1:4444`
- Docker publish rule: `0.0.0.0:4445 -> 4444/tcp`
- Persistent data volume: `contextforge-harness_contextforge-data`
- SQLite database: `/data/mcp.db`
- Reserved integration MCP backend port range: `9200-9299`

The named Docker volume has no explicit size cap. Initial gateway-only usage is
expected to stay small; use `scripts/volume-usage.sh` to inspect it.

## Setup

```sh
cd "$(git rev-parse --show-toplevel)/docker/contextforge-harness"
scripts/init-env.sh
scripts/prepare-volume.sh
docker compose -f compose.yml up -d
docker compose -f compose.yml ps
scripts/verify-auth.sh
```

The generated `env/contextforge.env` contains local admin and signing secrets
and is ignored by Git.

## Operations

```sh
docker compose -f compose.yml logs -f contextforge-gateway
docker compose -f compose.yml restart contextforge-gateway
scripts/volume-usage.sh
```

## Boundaries

- Do not register MCP services in this initial harness setup.
- Do not install MCP backend files or services inside the gateway container by
  default.
- Run stdio MCP backends beside a local or remote transceiver, then register the
  transceiver's validated `/sse` and `/mcp` endpoints with ContextForge.
- Expose both SSE and streamable HTTP for every MCP service when both transports
  validate as working.
- Run separate backend/transceiver instances on unique ports for services that
  are single-user by credential, project, client, or local state.
- Do not direct-write ContextForge database state.
- Use ContextForge API/Admin UI behavior for mutations.
- Keep host development gateway on `127.0.0.1:4444`.
