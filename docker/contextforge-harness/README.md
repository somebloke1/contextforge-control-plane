# ContextForge Container Harness

Isolated IBM ContextForge gateway harness for integration testing while the
host development gateway remains untouched.

This harness starts the stock ContextForge gateway and can start isolated
development MCP backend/transceiver sidecars. Registration is explicit; sidecar
startup alone does not register MCP services.

Service locality and the first MCP integration path are defined in
`SERVICE_LOCALITY.md`.

Evidence freshness and PR citation rules for this harness are defined in
`../../docs/dev-docker-client-evidence-freshness-protocol.md`.

Remote clients use the host/LAN/public ContextForge gateway address, not
backend sidecar addresses. The sidecar URLs in this document are upstream
registration targets used by the gateway from inside the Compose network.

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
- First dev MCP sidecar: `mentality-transceiver` on host
  `http://127.0.0.1:9201` and compose-network
  `http://mentality-transceiver:9201`
- Context7 dev MCP sidecar: `context7-transceiver` on host
  `http://127.0.0.1:9203` and compose-network
  `http://context7-transceiver:9203`
- Exa Search successor MCP sidecar: `exa-search-transceiver` on host
  `http://127.0.0.1:9205` and compose-network
  `http://exa-search-transceiver:9205`
- Playwright successor MCP sidecar: `playwright-transceiver` on host
  `http://127.0.0.1:9204` and compose-network
  `http://playwright-transceiver:9204`

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

If the Docker volume already exists, `env/contextforge.env` must match the admin
credentials in that volume. Use `scripts/ensure-env-auth.sh` before registration
or client validation. It is idempotent: it succeeds when the env matches, or can
copy a supplied ignored known-good env through `CONTEXTFORGE_DEV_ENV_SYNC_FROM`
without printing secret values.

## Dev MCP Transceiver

The first development sidecar fronts the repo-local `mentality` stdio MCP
backend with the stock ContextForge bridge. It uses a sanitized copy of the
governance ledgers inside the image and does not mount the host checkout by
default.

```sh
docker compose -f compose.yml up -d --build contextforge-gateway mentality-transceiver
scripts/probe-mentality-dev.py --direct-only
scripts/register_mentality_dev.py
scripts/probe-mentality-dev.py
```

`scripts/register_mentality_dev.py` registers
`http://mentality-transceiver:9201/mcp` as `mentality-dev-docker` through the
development gateway API at `http://127.0.0.1:4445`. It is idempotent by gateway
and virtual-server name and reads credentials only from ignored
`env/contextforge.env`.

`scripts/probe-mentality-dev.py` validates both surfaces. The direct probe
lists tools from `http://127.0.0.1:9201/mcp`. The virtual probe looks up the
registered server through the development gateway, creates a one-day scoped
catalog token for that server, lists tools through
`/servers/{server_id}/mcp/`, and revokes the probe token before exiting. The
script prints the token id only; it never prints the raw token value.

The harness enables `SSRF_ALLOW_PRIVATE_NETWORKS=true` because the isolated
development gateway must register compose-network upstreams such as
`http://mentality-transceiver:9201/mcp`. Do not copy this setting to the
legacy/live ContextForge surface without a separate approval and threat review.
It also sets `REQUIRE_USER_IN_DB=false` so the generated bootstrap admin can use
virtual MCP endpoints during disposable dev-harness validation.

## Context7 Dev MCP Transceiver

The Context7 sidecar fronts `@upstash/context7-mcp` through the same stock
bridge pattern, but it does not copy secret values into tracked files or images.
Export `CONTEXT7_API_KEY` from the ignored `server-instances/context7/.env`
before starting the sidecar:

```sh
set -a
source ../../server-instances/context7/.env
set +a
docker compose -f compose.yml up -d --build contextforge-gateway context7-transceiver
scripts/probe-context7-dev.py --direct-only
scripts/register_context7_dev.py
scripts/probe-context7-dev.py
```

`scripts/register_context7_dev.py` registers
`http://context7-transceiver:9203/mcp` as the canonical `context7-local`
gateway and `context7_local_server` virtual server in the development gateway.
The names intentionally match the project-init wrapper contract while the
registry, volume, token, and upstream process remain isolated to the dev Docker
surface.

## Exa Search Successor MCP Transceiver

The Exa Search sidecar fronts the repo-local Python backend in
`server-instances/exa-search/server.py` through the stock bridge. It reads
credentials from ignored `server-instances/exa-search/.env` through an optional
Compose `env_file`; do not copy or print secret values. A clean checkout can
still build and list Exa tools without that file, but actual Exa/Gemini calls
require the ignored credential env to be present.

```sh
docker compose -f compose.yml up -d --build contextforge-gateway exa-search-transceiver
python ../../scripts/plan_contextforge_docker_migration.py
```

The migration planner targets the compose-network URL
`http://exa-search-transceiver:9205/mcp`. Registry apply remains a separate
explicit step after credential-env preflight and direct reachability evidence.

## Playwright Successor MCP Transceiver

The Playwright sidecar runs `@playwright/mcp` with a Docker-local isolated
Chrome for Testing/Chromium runtime. It is a native MCP HTTP/SSE backend rather
than a `mcpgateway.translate` bridge. The sidecar uses an in-memory shared
browser context so stateful multi-tool workflows survive the ContextForge proxy
without sharing host browser/session state or writing a persistent browser
profile.

```sh
docker compose -f compose.yml up -d --build contextforge-gateway playwright-transceiver
python ../../scripts/plan_contextforge_docker_migration.py
```

The migration planner targets the compose-network URL
`http://playwright-transceiver:9204/mcp`. Registry apply remains a separate
explicit step after direct reachability evidence.

## Operations

```sh
docker compose -f compose.yml logs -f contextforge-gateway
docker compose -f compose.yml logs -f mentality-transceiver
docker compose -f compose.yml logs -f playwright-transceiver
docker compose -f compose.yml restart contextforge-gateway
scripts/volume-usage.sh
```

## Boundaries

- Register MCP services only into this development gateway unless a separate
  approval explicitly targets another surface.
- Keep client-facing and upstream address planes separate. Remote clients may
  originate from arbitrary IP-addressed hosts and must connect to the published
  ContextForge gateway URL with proper auth; they must not be asked to reach
  compose-internal backend names such as `playwright-transceiver`.
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
