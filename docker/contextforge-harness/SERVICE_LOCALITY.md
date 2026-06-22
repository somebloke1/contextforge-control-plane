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
| Shared canonical services such as `mentality`, `context7`, `playwright`, `ssh-tmux`, `exa-search`, and hosted/native services | Shared service or existing native endpoint | These services are not project-specific by default; duplicating them per project would create sibling identities, token scope drift, port churn, and extra lifecycle state without proving new behavior. |
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

Keep client and upstream address planes separate. Remote clients may come from
arbitrary IP-addressed hosts and should use the published ContextForge gateway
address, such as a LAN or public gateway URL with auth. Compose service names
and `127.0.0.1:920x` sidecar ports are upstream targets for ContextForge
registration and local diagnostics, not remote-client configuration values.

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

`ssh-tmux` follows compose-sidecar locality for the Docker successor surface:
`ssh-tmux-transceiver` runs build-installed `mcp-ssh-tmux` with
container-local tmux state and is registered through
`http://ssh-tmux-transceiver:9202/mcp` only after single-user/credential
boundary preflight and direct reachability evidence. Do not project or reuse
host tmux sessions by default; reset the container state instead of calculating
cleanup deltas.

`playwright` follows the same sidecar-locality principle with a native MCP
backend instead of a bridge: `playwright-transceiver` runs isolated Chrome for
Testing/Chromium in the harness network with an in-memory shared browser
context, and is registered through `http://playwright-transceiver:9204/mcp`
only after direct reachability evidence. Do not fall back to the host-loopback
`127.0.0.1:9104` live surface for Docker successor parity; the successor must
not inherit host browser or session residue.

`github` follows the same compose-sidecar-locality for credential-scoped stdio
backend: `github-transceiver` runs GitHub's maintained official
`github-mcp-server` binary in the Compose network through the stock
ContextForge bridge and is registered through
`http://github-transceiver:9206/mcp` only after token-boundary preflight and
direct reachability evidence. Keep the official server in stdio mode here:
native HTTP requires GitHub Authorization at the upstream HTTP boundary, while
the bridge keeps credentials inside the ignored `server-instances/github/.env`
sidecar boundary. Do not pass host shell token variables through Compose and do
not persist secrets in tracked files.

`web-search` follows the same compose-sidecar-locality for credential-scoped stdio
backend: `web-search-transceiver` runs the local `web_search/dist/mcp-server.js`
bundle through the stock bridge in the harness network and is registered through
`http://web-search-transceiver:9207/mcp` only after credential-env preflight and
direct reachability evidence. The image uses the sibling `web_search` checkout
as a named Compose build context and copies only package metadata plus
TypeScript sources into the image; inspect that checkout before treating runtime
evidence as canonical. Use the ignored `server-instances/web-search/.env`
boundary; do not persist secrets in tracked files.

`time` follows the same compose-sidecar-locality for the first onboarding
development foil: `time-transceiver` runs build-installed `mcp-server-time`
through the stock bridge in the harness network and is registered through
`http://time-transceiver:9209/mcp` only after direct reachability evidence. It
is stateless except for the configured local timezone default and does not
require credentials. Treat this as onboarding-factory proof material, not a
canonical post-development service set decision.

`serena-cf-controlplane-d46fe58a2a20` is project-scoped and remains owned by the
canonical host project instance on `127.0.0.1:9108`. Because Docker cannot reach
host loopback through `host.docker.internal`, the successor surface uses
`serena-cf-controlplane-proxy`, a host-network proxy bound only to Docker's
host-gateway address `172.17.0.1:9208`. Register
`http://host.docker.internal:9208/mcp` with the Docker gateway only after
proving the proxy and preserving the virtual-server exclusion of
`activate_project`. Treat `172.17.0.1` as a current-host Docker bridge
projection that must be preflighted; rootless Docker or custom bridge networks
may require a different host-gateway bind address.

Session-scoped services also require stateful gateway ingress. The Docker
harness sets `USE_STATEFUL_SESSIONS=true` and `GUNICORN_WORKERS=1` so the
downstream `Mcp-Session-Id` can bind to one process-local upstream MCP session
across a multi-tool workflow. Do not raise gateway worker count for
session-scoped parity unless a deliberate session-affinity backend is added and
verified.
