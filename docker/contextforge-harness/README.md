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
- SSH/tmux successor MCP sidecar: `ssh-tmux-transceiver` on host
  `http://127.0.0.1:9202` and compose-network
  `http://ssh-tmux-transceiver:9202`
- Context7 dev MCP sidecar: `context7-transceiver` on host
  `http://127.0.0.1:9203` and compose-network
  `http://context7-transceiver:9203`
- Exa Search successor MCP sidecar: `exa-search-transceiver` on host
  `http://127.0.0.1:9205` and compose-network
  `http://exa-search-transceiver:9205`
- GitHub successor MCP sidecar: `github-transceiver` on host
  `http://127.0.0.1:9206` and compose-network
  `http://github-transceiver:9206`
- Playwright successor MCP sidecar: `playwright-transceiver` on host
  `http://127.0.0.1:9204` and compose-network
  `http://playwright-transceiver:9204`
- Web Search successor MCP sidecar: `web-search-transceiver` on host
  `http://127.0.0.1:9207` and compose-network
  `http://web-search-transceiver:9207`
- Time development-foil MCP sidecar: `time-transceiver` on host
  `http://127.0.0.1:9209` and compose-network
  `http://time-transceiver:9209`
- Serena cf-controlplane host proxy: `serena-cf-controlplane-proxy` on Docker
  host-gateway `http://172.17.0.1:9208`, forwarding to host loopback
  `http://127.0.0.1:9108`

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

## SSH/tmux Successor MCP Transceiver

The SSH/tmux sidecar fronts build-installed `mcp-ssh-tmux` through the stock
ContextForge bridge in a dedicated container. It installs `tmux`,
`openssh-client`, and the MCP package during image build, exposes host
`127.0.0.1:9202`, and uses compose-network upstream
`http://ssh-tmux-transceiver:9202/mcp`.

This sidecar intentionally does not reuse host tmux state. Container-local tmux
state makes reset behavior idempotent and avoids silently sharing host SSH
sessions with remote clients. Listing tools or sessions is a safe transport
proof; opening remote SSH sessions, sending keys, reading files, or writing files
still requires explicit user intent and suitable SSH credentials inside the
sidecar boundary.

For live authenticated ssh-tmux semantic tests, place target details in the
ignored `../../server-instances/ssh-tmux/.env` file. Start from
`../../server-instances/ssh-tmux/.env.example` and replace the dummy values:

```sh
cp ../../server-instances/ssh-tmux/.env.example ../../server-instances/ssh-tmux/.env
mkdir -p ../../server-instances/ssh-tmux/auth
```

The harness reads that env file into `ssh-tmux-transceiver` when present and
mounts ignored host files from `../../server-instances/ssh-tmux/auth/` at
`/run/contextforge-ssh-tmux` inside the sidecar. For key auth, place the private
key at `../../server-instances/ssh-tmux/auth/id_ed25519` and known-hosts file at
`../../server-instances/ssh-tmux/auth/known_hosts`, then keep the default
container paths in `.env`. For password auth, set
`CONTEXTFORGE_SSH_TMUX_TEST_AUTH_MODE=password` and
`CONTEXTFORGE_SSH_TMUX_TEST_PASSWORD` in the ignored `.env`; the sidecar-local
SSH wrapper injects it with `sshpass -e` so the password is not supplied to the
tested assistant or printed in command arguments. The tested assistant can use
the non-secret alias from `CONTEXTFORGE_SSH_TMUX_TEST_ALIAS`, defaulting to
`contextforge-live-target`, instead of seeing the real host value. Do not commit
the real `.env`, private keys, passwords, or known-hosts material.

The migration planner targets the compose-network URL
`http://ssh-tmux-transceiver:9202/mcp`. Registry apply remains a separate
explicit step after sidecar reachability and single-user/credential boundary
preflight.

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

## GitHub Successor MCP Transceiver

The GitHub sidecar fronts GitHub's maintained official MCP server
(`ghcr.io/github/github-mcp-server:v1.4.0`) through the stock ContextForge
bridge. The image copies the pinned official binary from GHCR and runs
`github-mcp-server stdio` behind `mcpgateway.translate`. This keeps
ContextForge registration on the bridge-owned `/mcp` and `/sse` surfaces while
avoiding the deprecated `@modelcontextprotocol/server-github` npm package.

The official server also supports native HTTP, but that mode enforces GitHub
Authorization at the upstream HTTP boundary. The harness deliberately keeps the
stdio bridge so credentials remain inside the sidecar env-file boundary instead
of requiring ContextForge to forward GitHub PAT headers. It reads credentials
from ignored `server-instances/github/.env` via an optional Compose `env_file`.
Do not pass host shell API-token variables through Compose, and do not copy or
print token values. A clean checkout can build the image, but the sidecar must
fail fast unless the ignored env file supplies `GITHUB_PERSONAL_ACCESS_TOKEN`;
otherwise the bridge can expose a misleading transport surface after the
upstream stdio server exits.

```sh
docker compose -f compose.yml up -d --build contextforge-gateway github-transceiver
```

The migration planner targets the compose-network URL
`http://github-transceiver:9206/mcp`. Registry apply remains a separate explicit
step after credential-env preflight and direct reachability evidence.

## Playwright Successor MCP Transceiver

The Playwright sidecar runs `@playwright/mcp` with a Docker-local isolated
Chrome for Testing/Chromium runtime. It is a native MCP HTTP/SSE backend rather
than a `mcpgateway.translate` bridge. The sidecar uses an in-memory shared
browser context so stateful multi-tool workflows survive the ContextForge proxy
without sharing host browser/session state or writing a persistent browser
profile. The image installs `@playwright/mcp@0.0.76` at build time and runs the
installed `playwright-mcp` binary at runtime.

The harness gateway enables stateful Streamable HTTP sessions and runs a single
Gunicorn worker. Both are intentional: ContextForge binds upstream MCP client
state to the downstream `Mcp-Session-Id`, and the current upstream-session
registry is process-local unless a separate session-affinity backend is
configured. Without those settings, stateful workflows can degrade into
per-call upstream sessions.

Dev probe scripts disable optional MCP DELETE-session cleanup when using
server-scoped probe tokens. The probe success criterion is initialize/list/call
through the virtual MCP endpoint plus revocation of the ephemeral token through
the ContextForge token API; it is not proof that the same scoped token can
terminate a gateway session.

```sh
docker compose -f compose.yml up -d --build contextforge-gateway playwright-transceiver
python ../../scripts/plan_contextforge_docker_migration.py
```

The migration planner targets the compose-network URL
`http://playwright-transceiver:9204/mcp`. Registry apply remains a separate
explicit step after direct reachability evidence.

## Web Search Successor MCP Transceiver

The Web Search sidecar fronts the repo-local stdio MCP server in
`/home/dgk/workspace/web_search/dist/mcp-server.js` through the stock
ContextForge bridge. It runs in a dedicated container and reads credentials from
ignored `server-instances/web-search/.env` via an optional Compose `env_file`.
The image build uses the sibling `web_search` checkout as a named Compose build
context, not as the primary cf-controlplane context. The Dockerfile copies only
package metadata and TypeScript sources from that named context, runs
`npm run build`, then prunes development dependencies. Inspect the sibling
checkout state before relying on runtime evidence from this sidecar.
Do not copy or print API key or token values. A clean checkout can still build
and reach transport checks; provider-dependent tool behavior requires appropriate
credential values.

```sh
docker compose -f compose.yml up -d --build contextforge-gateway web-search-transceiver
python ../../scripts/plan_contextforge_docker_migration.py
```

The migration planner targets the compose-network URL
`http://web-search-transceiver:9207/mcp`. Registry apply remains a separate
explicit step after credential-env preflight and direct reachability evidence.

## Time Development-Foil MCP Transceiver

The Time sidecar fronts `mcp-server-time` through the stock ContextForge bridge
on reserved port `9209`. It is the first onboarding development foil, not a
canonical post-development service set decision. It uses a Docker-local
`LOCAL_TIMEZONE`, defaulting to `UTC`, and does not require credentials.

```sh
docker compose -f compose.yml up -d --build contextforge-gateway time-transceiver
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/probe-time-dev.py --direct-only
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/register_time_dev.py
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/probe-time-dev.py
```

`scripts/register_time_dev.py` registers
`http://time-transceiver:9209/mcp` as `time-dev-docker` and
`time_dev_docker_server` in the development gateway. It is idempotent by
gateway and virtual-server name and reads credentials only from ignored
`env/contextforge.env`.

`scripts/probe-time-dev.py` validates both surfaces. The direct probe lists
tools from `http://127.0.0.1:9209/mcp` and calls `get_current_time` with
`timezone=UTC`. The virtual probe creates a one-day scoped token for the Time
server, lists tools through `/servers/{server_id}/mcp/`, calls the same safe
tool, and revokes the probe token before exiting. This proves only the
development gateway surface it exercised; target-client readiness still needs
Pi/OpenCode/Codex-visible list-tools plus safe-call evidence.

## Serena cf-controlplane Host Proxy

The Serena cf-controlplane service is project-scoped to the canonical host
checkout `/home/dgk/workspace/cf-controlplane` and already runs as a native
streamable HTTP backend on host loopback `127.0.0.1:9108`. Docker containers
cannot reach that loopback listener through `host.docker.internal`.

The harness therefore uses `serena-cf-controlplane-proxy`, a constrained
host-network proxy that binds only the Docker host-gateway address
`172.17.0.1:9208` and forwards to `127.0.0.1:9108`. The gateway registers
`http://host.docker.internal:9208/mcp`; remote clients still use only the
published ContextForge gateway URL, never the proxy or upstream address.

This is not a general host rebind and not a project-mounted Serena sidecar. The
canonical Serena service remains host/project-scoped, `activate_project` must
remain excluded from the ContextForge virtual server, and runtime proof must
show the proxy plus virtual server before claiming parity. The fixed
`172.17.0.1` binding is a current-host Docker bridge projection, not a portable
assumption for rootless Docker or custom bridge networks; run the proxy
preflight before any Serena apply.

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
