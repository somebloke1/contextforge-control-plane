# Decisions

This ledger records project decisions with enough context for future agents to
preserve continuity. Entries use stable IDs, finite status values, repository
metadata, tags, and `governance-crud` comment anchors.

<!-- governance-crud:start id=dec-20260528-0001 -->
## dec-20260528-0001: Keep repo-local governance CRUD services

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: governance,crud,mcp,continuity

Keep `DECISIONS.md`, `ABEYANT_INTENTIONS.md`, and `OPEN_QUESTIONS.md` as the
durable repo-local governance registries. Manage them with
`scripts/governance_crud.py` and expose them through the stdio MCP service in
`scripts/governance_mcp.py` named `mentality`.
<!-- governance-crud:end id=dec-20260528-0001 -->

<!-- governance-crud:start id=dec-20260528-0002 -->
## dec-20260528-0002: Preserve branch, hook, ignore, and uv environment policy

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: git,hooks,python,uv

Keep main protected by tracked hooks in .githooks/, keep core.hooksPath set to .githooks, create agent work from dev-root, and preserve the project .gitignore. The active local work branch is agent/contextforge-bootstrap; the prior old-name bootstrap branch was renamed so ContextForge terminology is consistent outside the root directory path. Use the existing uv-created .venv for Python work and install dependency changes with the currently supported uv pip install --python .venv/bin/python ... syntax.
<!-- governance-crud:end id=dec-20260528-0002 -->

<!-- governance-crud:start id=dec-20260528-0003 -->
## dec-20260528-0003: Use stock IBM ContextForge as the gateway implementation

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,mcpgateway,stock,architecture

Install and operate the package-provided IBM ContextForge MCP Gateway
(`mcp-contextforge-gateway`, entry point `mcpgateway`) instead of maintaining
project-local duplicate gateway, translator, registration, or generated service
fleet implementations. Project code should configure, verify, and document the
stock application rather than reimplementing its runtime responsibilities.
<!-- governance-crud:end id=dec-20260528-0003 -->

<!-- governance-crud:start id=dec-20260528-0004 -->
## dec-20260528-0004: Bridge only missing transports with package support

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: mcp,transport,bridge,contextforge

Register services through native ContextForge mechanisms whenever they already
provide suitable HTTP or SSE access. Use package-provided bridge or translation
support only when a discovered service lacks a required transport: stdio servers
need HTTP and SSE exposure, SSE-only servers need only HTTP exposure, and
HTTP-only servers need only SSE exposure.
<!-- governance-crud:end id=dec-20260528-0004 -->

<!-- governance-crud:start id=dec-20260528-0005 -->
## dec-20260528-0005: Verify the clean gateway before external registrations

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: verification,sequence,contextforge,operations

The restart sequence must prove the stock gateway starts cleanly and responds
to local health/admin probes before registering external MCP servers, REST/API
tools, or hosted services. Runtime claims require evidence from current files,
commands, service state, admin API/UI behavior, and endpoint probes.
<!-- governance-crud:end id=dec-20260528-0005 -->

<!-- governance-crud:start id=dec-20260528-0006 -->
## dec-20260528-0006: Keep runtime secrets and installed state out of Git

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: secrets,systemd,local-state,security

Do not commit real API keys, bearer tokens, passwords, generated JWTs, database
files, or client-local secret values. Keep runtime env files in ignored local
paths such as `config/contextforge.env` or installed `/etc/contextforge/*.env`
files. System-level activation remains a root operation because this user
cannot write `/etc/systemd/system`, `/opt`, or `/var/lib` without sudo.
<!-- governance-crud:end id=dec-20260528-0006 -->

<!-- governance-crud:start id=dec-20260528-0007 -->
## dec-20260528-0007: Register governance service as first stock stdio bridge proof

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,registration,stdio,governance,verification

The first external service class proof uses stock package behavior only. scripts/governance_mcp.py remains a repo-local stdio MCP server. python -m mcpgateway.translate exposes it on 127.0.0.1:9100 with both /sse and /mcp. Real MCP client probes listed five governance CRUD tools on both direct bridge transports. ContextForge now registers http://127.0.0.1:9100/sse as gateway mentality, imports five tools, exposes virtual server mentality_server via /servers with the required top-level server payload, and MCP client probes list those five tools through /servers/{id}/mcp/ and /servers/{id}/sse.
<!-- governance-crud:end id=dec-20260528-0007 -->

<!-- governance-crud:start id=dec-20260528-0008 -->
## dec-20260528-0008: Give every exposed service a server-instances backend home

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: server-instances,contextforge,backends,registration,operations

Every service exposed through ContextForge must have a concrete upstream backend home under server-instances/<service-slug>/ or an explicitly documented equivalent. The directory records the backend MCP server or REST/API source ContextForge points at: sanitized instance manifest, package bridge command when a bridge is needed, native endpoint metadata when no bridge is needed, health probes, and registration notes. Runtime env, logs, local DBs, and probe outputs inside each instance remain ignored. These directories are not a custom duplicate gateway or generated service fleet; stock ContextForge remains the registry/proxy, native HTTP/SSE services are preserved directly, and mcpgateway.translate is used only to expose missing transports.
<!-- governance-crud:end id=dec-20260528-0008 -->

<!-- governance-crud:start id=dec-20260528-0009 -->
## dec-20260528-0009: Use local self-signed TLS for the ContextForge gateway

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: https,tls,self-signed,contextforge,local-runtime

Superseded by dec-20260528-0043 for this workstation. The local gateway originally used repo-local ignored self-signed TLS, but direct MCP clients failed normal launch unless local CA environment was injected. The user accepted plain loopback HTTP, so contextforge-gateway.service now runs mcpgateway on 127.0.0.1:4444 without ssl-certfile or ssl-keyfile, and config/contextforge.env sets SSL=false with an http APP_DOMAIN. Keep the ignored config/tls files only as optional future material if local TLS is reintroduced.
<!-- governance-crud:end id=dec-20260528-0009 -->

<!-- governance-crud:start id=dec-20260528-0010 -->
## dec-20260528-0010: Keep backend instance directories separate from ContextForge runtime ownership

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: server-instances,contextforge,backends,architecture

server-instances/<service-slug>/ directories are the operational homes for backend MCP servers, REST APIs, bridge launch commands, probes, and sanitized registration metadata. They do not own ContextForge's registry, proxy, database, admin UI, virtual servers, or transport implementation. Stock ContextForge remains the runtime authority; instance directories document and launch the upstreams that ContextForge registers natively or reaches through package-provided bridge support.
<!-- governance-crud:end id=dec-20260528-0010 -->

<!-- governance-crud:start id=dec-20260528-0011 -->
## dec-20260528-0011: Use official source install when PyPI wheel omits Admin UI bundle

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,admin-ui,install,upstream,stock

The PyPI wheel for mcp-contextforge-gateway 1.0.2 installed successfully but did not include the referenced Vite Admin UI bundle. Live evidence: /static/bundle-DuE_HYmb.js returned 404, sidebar clicks changed the hash but left the main panel stuck, and the console reported missing Admin UI functions. The matching IBM v1.0.2 source tag includes mcpgateway/admin_ui sources and a documented Makefile build-ui path that runs npm install/ci plus npm run build:css and npm run vite:build. For this local install, keep uv and install mcp-contextforge-gateway 1.0.2 from the official v1.0.2 source checkout under ignored upstream/contextforge-v1.0.2 after building the stock Admin UI bundle. This is a source-install workaround for an upstream packaging defect, not a ContextForge-native code patch and not a custom gateway implementation.
<!-- governance-crud:end id=dec-20260528-0011 -->

<!-- governance-crud:start id=dec-20260528-0012 -->
## dec-20260528-0012: Allocate bridge ports deterministically in server-instances manifests

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: server-instances,ports,bridges,inventory

This pre-deduplication port allocation policy is superseded by dec-20260528-0019 and dec-20260528-0027. Current service homes are canonical, not client-prefixed: mentality uses 127.0.0.1:9100, ssh-tmux uses 127.0.0.1:9102, context7 uses 127.0.0.1:9103, and playwright uses 127.0.0.1:9104. Remote native services such as Exa Search and OpenZeppelin Solidity Contracts have documented server-instances homes but no local bridge ports.
<!-- governance-crud:end id=dec-20260528-0012 -->

<!-- governance-crud:start id=dec-20260528-0013 -->
## dec-20260528-0013: Register opencode fetch-mcp as second stdio bridge proof

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,registration,stdio,fetch-mcp,verification

opencode-fetch-mcp was a controlled stdio registration proof. It is superseded by dec-20260528-0020, which excludes fetch from the current canonical service set and removed the ContextForge records.
<!-- governance-crud:end id=dec-20260528-0013 -->

<!-- governance-crud:start id=dec-20260528-0014 -->
## dec-20260528-0014: Register opencode filesystem as controlled stdio bridge

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,registration,stdio,filesystem,verification

opencode-filesystem was a controlled stdio bridge proof. It is superseded by dec-20260528-0020, which excludes filesystem MCP services from the current canonical service set and removed the ContextForge records.
<!-- governance-crud:end id=dec-20260528-0014 -->

<!-- governance-crud:start id=dec-20260528-0015 -->
## dec-20260528-0015: Register opencode code-index as controlled stdio bridge

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,registration,stdio,code-index,verification

opencode-code-index was a controlled stdio bridge proof. It is superseded by dec-20260528-0021, which excludes code-index MCP services from the current canonical service set and removed the ContextForge records.
<!-- governance-crud:end id=dec-20260528-0015 -->

<!-- governance-crud:start id=dec-20260528-0016 -->
## dec-20260528-0016: Register gemini-cli filesystem as controlled stdio bridge

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,registration,stdio,filesystem,verification

gemini-cli filesystem was a controlled stdio bridge proof. It is superseded by dec-20260528-0020, which excludes filesystem MCP services from the current canonical service set and removed the ContextForge records.
<!-- governance-crud:end id=dec-20260528-0016 -->

<!-- governance-crud:start id=dec-20260528-0017 -->
## dec-20260528-0017: Register gemini-cli code-index as controlled stdio bridge

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,registration,stdio,code-index,verification

gemini-cli code-index was a controlled stdio bridge proof. It is superseded by dec-20260528-0021, which excludes code-index MCP services from the current canonical service set and removed the ContextForge records.
<!-- governance-crud:end id=dec-20260528-0017 -->

<!-- governance-crud:start id=dec-20260528-0018 -->
## dec-20260528-0018: Prefer standard Exa MCP gateway over local web_search wrapper

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,registration,exa,deduplication,native

Superseded by dec-20260528-0030. The standard hosted Exa MCP gateway at https://mcp.exa.ai/mcp is no longer the preferred or registered Exa service for this ContextForge install. Exa Search now uses the local server-instances/exa-search backend with EXA_API_KEY and GEMINI_API_KEY, bridged on http://localhost:9105/mcp and exposed through ContextForge as the replacement Exa Search gateway.
<!-- governance-crud:end id=dec-20260528-0018 -->

<!-- governance-crud:start id=dec-20260528-0019 -->
## dec-20260528-0019: Use canonical service identity instead of discovery-client names

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,inventory,deduplication,naming,governance

MCP client configs from Codex, Claude, Gemini, and OpenCode are discovery sources, not service identities. ContextForge registrations should be deduplicated by actual backend package/server, runtime scope, credential scope, and exposed resource scope. Service names should be canonical service names rather than names derived from the assistant config where the service was discovered. Duplicate registrations should exist only when runtime behavior is materially different.
<!-- governance-crud:end id=dec-20260528-0019 -->

<!-- governance-crud:start id=dec-20260528-0020 -->
## dec-20260528-0020: Exclude fetch, ZAI, Gemini tools, and filesystem services for now

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,scope,exclusion,deduplication

Per user direction, fetch, zai-mcp-server, gemini-tools, and filesystem MCP services are out of current registration scope. The previously registered opencode_fetch_mcp, opencode_filesystem, and gemini_cli_filesystem ContextForge records were removed through the stock API. Exa Search remains in scope, but dec-20260528-0030 supersedes the earlier hosted Exa representation with a local server-instances/exa-search backend.
<!-- governance-crud:end id=dec-20260528-0020 -->

<!-- governance-crud:start id=dec-20260528-0021 -->
## dec-20260528-0021: Exclude code-index MCP services for now

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,scope,exclusion,code-index

Per user direction, code-index MCP services are out of current registration scope. The previously registered opencode_code_index and gemini_cli_code_index ContextForge records were removed through the stock API, and their bridge processes were stopped.
<!-- governance-crud:end id=dec-20260528-0021 -->

<!-- governance-crud:start id=dec-20260528-0022 -->
## dec-20260528-0022: Rename governance MCP service to mentality

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,governance,naming,registration

The repository-local governance MCP service is now named mentality. The prior governance-named ContextForge gateway and virtual server were deleted through the stock API, then recreated as gateway mentality and virtual server mentality_server. The local backend home moved to server-instances/mentality, scripts/governance_mcp.py now advertises FastMCP('mentality'), and direct plus ContextForge virtual MCP/SSE probes list the expected five governance CRUD tools.
<!-- governance-crud:end id=dec-20260528-0022 -->

<!-- governance-crud:start id=dec-20260528-0023 -->
## dec-20260528-0023: Register canonical Context7 service

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,context7,deduplication,registration,verification

Registered one canonical context7 service instead of one per assistant config. Native HTTP mode for @upstash/context7-mcp was checked, but it requires UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN, which were not present in the discovered configs. The configured stdio backend is exposed with mcpgateway.translate on 127.0.0.1:9103. Direct /mcp and /sse probes listed resolve-library-id and query-docs. ContextForge gateway c8e2bd7d99254b98b2904bce6f39aedc and virtual server context7_local_server d321bc2a620b43fca1f31f6ee61d1ba0 expose context7-local-resolve-library-id and context7-local-query-docs, plus matching tool-bound prompts and resources.
<!-- governance-crud:end id=dec-20260528-0023 -->

<!-- governance-crud:start id=dec-20260528-0024 -->
## dec-20260528-0024: Run canonical ContextForge stack under user systemd

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,systemd,user-service,verification

Installed user-level systemd units for the canonical local ContextForge stack: contextforge-gateway, contextforge-mentality, contextforge-ssh-tmux, contextforge-context7, contextforge-playwright, contextforge-exa-search, contextforge-github, and contextforge-web-search, with contextforge.target enabled. Ad hoc port owners were stopped and services were started through systemctl --user. Direct MCP/SSE probes and ContextForge virtual MCP/SSE probes passed against the systemd-managed processes.
<!-- governance-crud:end id=dec-20260528-0024 -->

<!-- governance-crud:start id=dec-20260528-0025 -->
## dec-20260528-0025: Represent standard Exa Search as canonical remote service

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,exa,registration,remote,verification

Superseded by dec-20260528-0030. Exa Search is no longer represented as a canonical remote hosted service at https://mcp.exa.ai/mcp. It has been replaced through the ContextForge API by the local server-instances/exa-search backend exposed on http://localhost:9105/mcp with three tools, including exa-search-web-search-gemini-exa.
<!-- governance-crud:end id=dec-20260528-0025 -->

<!-- governance-crud:start id=dec-20260528-0026 -->
## dec-20260528-0026: Represent OpenZeppelin Solidity Contracts as canonical remote service

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,openzeppelin,solidity,remote,verification

An enabled user-added OpenZeppelin Solidity Contracts gateway was present at https://mcp.openzeppelin.com/contracts/solidity/mcp using STREAMABLEHTTP. Added server-instances/openzeppelin-solidity-contracts as the canonical remote service home and created openzeppelin_solidity_contracts_server over the existing eight OpenZeppelin tools. ContextForge virtual /mcp/ and /sse probes listed all eight tools.
<!-- governance-crud:end id=dec-20260528-0026 -->

<!-- governance-crud:start id=dec-20260528-0027 -->
## dec-20260528-0027: Clean registry contains only canonical active services

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,registry,cleanup,verification

Registry cleanup and service replacement are now governed by the canonical active service set. Earlier disabled out-of-scope registry rows for GitHub, Globalping, Indeed, and Parallel Search were removed through the stock gateway API. GitHub was reintroduced intentionally by dec-20260528-0034, and web-search was promoted by dec-20260528-0035 after live backend probing. Current registry verification should expect eight active gateways, eight virtual servers, and 80 active tools: mentality, ssh-tmux, context7, playwright, exa-search, OpenZeppelin Solidity Contracts, GitHub, and web-search.
<!-- governance-crud:end id=dec-20260528-0027 -->

<!-- governance-crud:start id=dec-20260528-0028 -->
## dec-20260528-0028: Use CSRF_EXEMPT_PATHS for local Admin UI API cookie-auth endpoints

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,csrf,admin-ui,configuration,local-runtime

The stock Admin UI uses an HttpOnly `jwt_token` session cookie for interactive admin login. That session JWT is distinct from cataloged ContextForge API tokens created by `/tokens` and later used as bearer credentials for MCP/server access. Browser JavaScript cannot always read the session JWT to send an Authorization header, so some Admin UI JavaScript endpoints, including `/api/logs/search` and `/tokens`, hit the global HMAC CSRF middleware while carrying the admin-page double-submit CSRF cookie of the same name, causing `CSRF_TOKEN_INVALID`. For this local ContextForge installation, use the stock `CSRF_EXEMPT_PATHS` setting to add `/api/logs` and `/tokens` while keeping authentication and permission checks enabled. Verified with an Admin UI form-login cookie session: `/api/logs/search` returned 200, `/tokens` returned 201 for a temporary cataloged API token, and `DELETE /tokens/{id}` returned 204 to revoke it. Do not patch ContextForge source for this local workaround.
<!-- governance-crud:end id=dec-20260528-0028 -->

<!-- governance-crud:start id=dec-20260528-0029 -->
## dec-20260528-0029: Prohibit direct ContextForge database mutations

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,api,database,operations

ContextForge registry state must be changed through ContextForge API or Admin UI behavior, not by direct writes to the SQLite/Postgres database. Direct database reads are allowed for diagnosis and verification, but updates, deletes, inserts, association rewrites, and visibility/team edits against ContextForge-owned tables are prohibited unless the user explicitly authorizes an emergency repair after API paths have failed. This preserves ContextForge's validation, cache/session invalidation, audit metadata, ownership checks, and tool/resource association logic.
<!-- governance-crud:end id=dec-20260528-0029 -->

<!-- governance-crud:start id=dec-20260528-0030 -->
## dec-20260528-0030: Replace hosted Exa with local Exa plus Gemini backend

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,exa,server-instances

The Exa Search ContextForge service now points at the local server-instances/exa-search backend instead of the hosted https://mcp.exa.ai/mcp gateway. The local stdio FastMCP backend uses EXA_API_KEY and GEMINI_API_KEY from ignored server-instances/exa-search/.env and is exposed by mcpgateway.translate on 127.0.0.1:9105 with streamable HTTP and SSE. The prior Exa virtual server and hosted gateway were deleted through the ContextForge API, then Exa Search was recreated as gateway 05754613e3644721aa12f2d923dc6403 with URL http://localhost:9105/mcp and virtual server exa_search_server c8d6f6fdbb83456ba6350cd4c7e5c8bf over tools exa-search-web-fetch-exa, exa-search-web-search-exa, and exa-search-web-search-gemini-exa. Direct bridge /mcp and /sse probes passed, virtual ContextForge /mcp/ and /sse probes passed, and a virtual MCP call to exa-search-web-search-gemini-exa succeeded.
<!-- governance-crud:end id=dec-20260528-0030 -->

<!-- governance-crud:start id=dec-20260528-0031 -->
## dec-20260528-0031: Register tool-bound guidance as ContextForge prompts and resources

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/cf-controlplane
- Created: 2026-05-28
- Updated: 2026-06-20
- Tags: contextforge,prompts,resources,tool-guidance,api

For each active canonical MCP tool, register one succinct reusable prompt and one more comprehensive documentation resource through the ContextForge API, then associate both with the tool's canonical virtual server. Historical live registry proof covered 80 tools, 80 prompts, and 80 resources across mentality, ssh-tmux, context7, playwright, exa-search, OpenZeppelin Solidity Contracts, GitHub, and web-search. The current scripts/register_tool_guidance.py inventory defines 81 prompt/resource guidance entries across those canonical services; refreshed authenticated full-pagination API readback and MCP client readback are required before claiming current live 81/81 parity after service additions.
<!-- governance-crud:end id=dec-20260528-0031 -->

<!-- governance-crud:start id=dec-20260528-0032 -->
## dec-20260528-0032: Shape tool guidance content to satisfy ContextForge content security

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,content-security,sanitization,prompts,resources

ContextForge resource and prompt writes pass through stock content-security validation. The default scanner can reject normal documentation text containing Markdown code spans, fenced JSON, shell-like operators, template markers, or SQL-trigger words such as select, update, delete, drop, insert, and union followed by whitespace. Keep gateway validation enabled; do not relax global validation for this project-local documentation. scripts/register_tool_guidance.py therefore shapes generated guidance text deterministically, summarizes schemas as bullet fields instead of raw JSON, preflights with ContextForge's own validator, and retries API writes when rate-limited.
<!-- governance-crud:end id=dec-20260528-0032 -->

<!-- governance-crud:start id=dec-20260528-0033 -->
## dec-20260528-0033: Route client MCP configs through canonical ContextForge services

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,clients,mcp,ssh-tmux,http

Client configs route through canonical ContextForge services without client-derived service identities. OpenCode, Gemini CLI, and Claude Code now use direct authenticated HTTP virtual-server MCP URLs on http://127.0.0.1:4444 where their schemas support URL/header entries. Global Codex Terminal, Claude Desktop, project-local Codex web_search, and active PI MCP bridge sources still use ContextForge virtual-server stdio wrappers where the client is stdio-oriented or direct URL/header config has not been proven reliable. The legacy ssh-mcp client service name and @alolite/ssh-mcp backend command were removed from active target client configs and replaced by ssh_tmux pointing at ssh_tmux_server through ContextForge. Active PI ssh_execute/ssh_connections adapters route to ssh_tmux_server. The web_search project-local Codex entry and disabled global Codex exa_web_search entry point at web_search_server instead of launching /home/dgk/workspace/web_search/dist/mcp-server.js directly. OpenCode automatic OAuth against the local ContextForge endpoint remains separate from the working direct bearer-header HTTP path.
<!-- governance-crud:end id=dec-20260528-0033 -->

<!-- governance-crud:start id=dec-20260528-0034 -->
## dec-20260528-0034: Register canonical GitHub MCP service

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,github,registration,opencode,systemd,http

OpenCode direct stdio GitHub MCP entry using @modelcontextprotocol/server-github and a gh CLI token was deduplicated into one canonical ContextForge service. The backend home is server-instances/github, and contextforge-github.service runs the stock mcpgateway.translate bridge on 127.0.0.1:9106 with streamable HTTP and SSE. ContextForge API registration created gateway 35de0ef8f791449898317435f986d6dd and virtual server github_server over 26 discovered GitHub tools. scripts/register_tool_guidance.py registers matching prompts and resources for those tools. OpenCode now reaches github through direct authenticated local HTTP to the ContextForge github_server virtual-server MCP endpoint; GitHub credentials remain runtime bridge state and the gh token command is no longer embedded in the OpenCode client config.
<!-- governance-crud:end id=dec-20260528-0034 -->

<!-- governance-crud:start id=dec-20260528-0035 -->
## dec-20260528-0035: Register canonical web_search MCP service

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,web-search,registration,client-config

The standalone MCP server in /home/dgk/workspace/web_search is now promoted to a canonical ContextForge service named web-search. server-instances/web-search documents the backend, optional ignored env, and mcpgateway.translate bridge on 127.0.0.1:9107. ContextForge API registration created gateway 68493a5f5b5048f5973edb8c5d00dc5b and virtual server web_search_server 51a4c7adcdae4cc9a7cf9552c5858011 over tools web-search-code-search, web-search-fetch-content, web-search-github-repo, web-search-pdf-extract, and web-search-web-search. Direct stdio, bridge /mcp, bridge /sse, virtual /mcp, virtual /sse, and a virtual web-search-fetch-content call against https://example.com succeeded. Global disabled Codex exa_web_search and project-local web_search now point at the ContextForge wrapper instead of node /home/dgk/workspace/web_search/dist/mcp-server.js.
<!-- governance-crud:end id=dec-20260528-0035 -->

<!-- governance-crud:start id=dec-20260528-0036 -->
## dec-20260528-0036: Route active PI MCP bridge sources through ContextForge

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,pi,mcp-bridge,client-config

Active PI MCP bridge sources now keep their PI-facing tool names while routing backend MCP calls through canonical ContextForge virtual servers. The global bridge at /home/dgk/.pi/agent/extensions/mcp-bridge/index.ts now uses scripts/contextforge_mcp_wrapper.py for context7_local_server and playwright_server. The main project bridges at /home/dgk/workspace/noetic-pi/.pi/extensions/mcp-bridge/index.ts and /home/dgk/workspace/phronesis/.pi/extensions/mcp-bridge/index.ts now use the wrapper for context7_local_server, playwright_server, and ssh_tmux_server. The adapters normalize old upstream tool names such as resolve-library-id and browser_click to ContextForge-prefixed names, and map ssh_execute/ssh_connections to ssh-tmux open, send, list, and close operations. Variant/prep/closure/worktree/archive bridge copies remain documented as needing confirmation before bulk editing.
<!-- governance-crud:end id=dec-20260528-0036 -->

<!-- governance-crud:start id=dec-20260528-0037 -->
## dec-20260528-0037: Use direct ContextForge HTTP with env bearer header for OpenCode

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,opencode,http,auth

Superseded by dec-20260528-0043. OpenCode supports headers on remote MCP entries. The HTTPS form failed normal opencode mcp list with SSE error: self signed certificate, so the local gateway now runs on plain loopback HTTP instead of requiring client CA configuration. OpenCode canonical services now use direct authenticated HTTP virtual-server MCP URLs with oauth:false while preserving client-facing names and enabled state. OpenCode automatic OAuth against the local ContextForge endpoint remains separately open due CSRF_TOKEN_INVALID, but it is not needed for the bearer-header HTTP path.
<!-- governance-crud:end id=dec-20260528-0037 -->

<!-- governance-crud:start id=dec-20260528-0038 -->
## dec-20260528-0038: Use direct ContextForge HTTP for Gemini CLI and Claude Code

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,gemini-cli,claude-code,http,auth

Superseded by dec-20260528-0043. Gemini CLI and Claude Code support direct streamable HTTP MCP entries with request headers. The HTTPS form failed normal client MCP listing when local CA environment was absent, so the local gateway now runs on plain loopback HTTP instead of requiring client CA configuration. Their active global canonical service entries now use direct authenticated HTTP virtual-server MCP URLs for context7, playwright, ssh_tmux, mentality, exa_search, and openzeppelin_solidity_contracts.
<!-- governance-crud:end id=dec-20260528-0038 -->

<!-- governance-crud:start id=dec-20260528-0039 -->
## dec-20260528-0039: Declare project-scope contracts for canonical services

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,scope,inventory,client-config

Canonical service manifests now include explicit scope metadata. Among registered canonical services, only mentality requires local-project scope, and it signals that scope through the required repo tool argument on every governance CRUD call. ssh-tmux, context7, playwright, exa-search, OpenZeppelin Solidity Contracts, GitHub, and web-search are not local-project scoped; they are scoped by explicit request arguments, provider or account credentials, isolated runtime state, remote target/session arguments, or owner/repo style API arguments. Project-local governance MCP services discovered in other repositories remain candidates rather than centralized replacements until the user approves consolidating their repo-specific ledger scope into mentality or another canonical service.
<!-- governance-crud:end id=dec-20260528-0039 -->

<!-- governance-crud:start id=dec-20260528-0040 -->
## dec-20260528-0040: Treat ContextForge middleware as gateway policy, not transport replacement

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,middleware,rate-limit,plugins,http

ContextForge middleware is relevant for gateway policy but does not change the direct transport preference by itself. Stock middleware covers auth context, token scoping, protocol checks, validation, logging, CSRF, token usage, and configurable rate limiting. Tool plugin bindings provide per-tool execution hooks with modes such as sequential, concurrent, transform, audit, and fire-and-forget. Direct HTTP/SSE requests traverse the ContextForge middleware stack, so middleware is not a reason to add scripts/contextforge_mcp_wrapper.py. OpenCode, Gemini CLI, and Claude Code now use direct loopback HTTP per dec-20260528-0043. Use middleware/plugin bindings later for rate limits, validation, audit, or per-tool guardrails if needed; current local-project scope signaling remains the explicit mentality repo argument.
<!-- governance-crud:end id=dec-20260528-0040 -->

<!-- governance-crud:start id=dec-20260528-0041 -->
## dec-20260528-0041: Keep Claude Desktop canonical services on stdio wrapper

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,claude-desktop,client-config,http,wrapper

Keep Claude Desktop canonical MCP entries on scripts/contextforge_mcp_wrapper.py for this installed Desktop build. Local inspection of Claude Desktop 1.1348.0 app.asar showed the claude_desktop_config.json mcpServers schema accepts only command, optional args, optional string-valued env, and optional extensionId. Although the app bundle contains internal SSE and streamable HTTP client transports with request header support, those transports are not exposed by the local JSON config schema inspected here. Direct local url/headers entries would be classified as invalid MCP server configs and skipped, so the wrapper is the reliable no-login path for Claude Desktop until a supported local direct-HTTP config surface is found.
<!-- governance-crud:end id=dec-20260528-0041 -->

<!-- governance-crud:start id=dec-20260528-0042 -->
## dec-20260528-0042: Use wrappers for normal-launch MCP clients until local HTTPS trust is solved

- Ledger: decisions
- Status: superseded
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,opencode,gemini-cli,claude-code,tls,client-config

Superseded by dec-20260528-0043. The wrapper fallback was correct while the local gateway only exposed self-signed HTTPS, but the user accepted plain local HTTP for this host. The gateway now runs on http://127.0.0.1:4444, and OpenCode, Gemini CLI, and Claude Code use direct authenticated HTTP MCP entries. Claude Desktop remains wrapper-based because its installed local config schema accepts only command/args/env-style stdio entries.
<!-- governance-crud:end id=dec-20260528-0042 -->

<!-- governance-crud:start id=dec-20260528-0043 -->
## dec-20260528-0043: Run the local ContextForge gateway over HTTP for direct-capable clients

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,http,opencode,gemini-cli,claude-code,client-config

For this local workstation, reliable direct MCP operation is more important than avoiding plain loopback HTTP. The user explicitly accepted HTTP instead of local TLS trust workarounds. The user-level contextforge-gateway.service now starts mcpgateway on 127.0.0.1:4444 without ssl-certfile or ssl-keyfile, config/contextforge.env has SSL=false plus http APP_DOMAIN and ALLOWED_ORIGINS, and scripts/contextforge_mcp_wrapper.py defaults to http://127.0.0.1:4444 while retaining optional HTTPS handling. OpenCode, Gemini CLI, and Claude Code canonical entries now use direct authenticated HTTP virtual-server MCP URLs with bearer headers. Verified without NODE_EXTRA_CA_CERTS, SSL_CERT_FILE, or REQUESTS_CA_BUNDLE: opencode mcp list connects context7, github, ssh_tmux, mentality, exa_search, and openzeppelin_solidity_contracts with playwright preserved disabled; claude mcp list connects context7, playwright, ssh_tmux, mentality, exa_search, and openzeppelin_solidity_contracts over HTTP; gemini mcp list connects context7, playwright, ssh_tmux, mentality, exa_search, and openzeppelin_solidity_contracts over HTTP. Claude Desktop remains wrapper-based because its installed local JSON schema does not expose URL/header MCP entries.
<!-- governance-crud:end id=dec-20260528-0043 -->

<!-- governance-crud:start id=dec-20260528-0044 -->
## dec-20260528-0044: Route AnythingLLM Context7 through canonical ContextForge service

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-05-28
- Tags: contextforge,anythingllm,context7,deduplication,client-config

The expanded global inventory found AnythingLLM configured with a context7 MCP server launching @upstash/context7-mcp directly. Because context7 is already a canonical registered ContextForge service and the AnythingLLM config is stdio-shaped, /home/dgk/.config/anythingllm-desktop/storage/plugins/anythingllm_mcp_servers.json now preserves the client-facing name context7 but launches scripts/contextforge_mcp_wrapper.py context7_local_server through the repo .venv Python. This removes a parallel client-owned Context7 backend and keeps ContextForge as the service identity. JSON syntax was validated and active target config grep no longer finds @upstash/context7-mcp, CONTEXT7_API_KEY, or the prior local key pattern in client configs.
<!-- governance-crud:end id=dec-20260528-0044 -->

<!-- governance-crud:start id=dec-20260528-0045 -->
## dec-20260528-0045: Inventory project-root Claude Code config files

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-28
- Updated: 2026-06-16
- Tags: inventory,claude-code,workspace,filesystem,exclusion

The workspace inventory now treats project-root .claude.json files as Claude Code project configs, not generic workspace files. This added /home/dgk/workspace/home_tech_assistant/.claude.json to the inventory as a claude-code-project entry. Its filesystem-project MCP server is classified under the existing filesystem exclusion, matching the paired home_tech_assistant opencode filesystem entry. The 2026-05-28 inventory report totaled 200 entries, 183 enabled, with 46 stdio and 19 streamable HTTP transports. A 2026-06-16 refresh from clean branch `codex/service-inventory-triage` now finds 207 entries, 203 enabled, with 72 stdio and 6 streamable HTTP transports; the classification remains exclusion/project-local/candidate based rather than client-name based.
<!-- governance-crud:end id=dec-20260528-0045 -->

<!-- governance-crud:start id=dec-20260529-0046 -->
## dec-20260529-0046: Keep Serena project-scoped and project-local in Codex

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-29
- Updated: 2026-05-29
- Tags: contextforge,serena,codex,project-scope,client-config

Serena remains exposed through ContextForge, but it must not be a global Codex MCP server because the backend is stateful and scoped to one workspace. The global `~/.codex/config.toml` Serena entry was removed, and the cf-controlplane project-local `.codex/config.toml` now owns the `serena` MCP entry that launches `scripts/contextforge_mcp_wrapper.py serena_cf_controlplane_d46fe58a2a20_server` with cwd `/home/dgk/workspace/legacy-controlplane-archive`. The ContextForge virtual server excludes Serena's `activate_project` tool; project selection is controlled by the service and client project configuration, not by an LLM-callable project switch that could target `/` or `/home/dgk`. Current verification: `codex mcp list` from `/home/dgk` shows no Serena entry, `codex mcp list` from `/home/dgk/workspace/legacy-controlplane-archive` shows one ContextForge-backed `serena` entry, and a wrapper `tools/list` smoke test reports 22 tools without `serena-cf-controlplane-d46fe58a2a20-activate-project`.
<!-- governance-crud:end id=dec-20260529-0046 -->

<!-- governance-crud:start id=dec-20260529-0047 -->
## dec-20260529-0047: Initialize projects through ContextForge-owned hook and per-project Serena manager

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-29
- Updated: 2026-05-29
- Tags: contextforge,serena,codex,project-init,hooks

Project initialization is now delivered by the global Codex SessionStart/UserPromptSubmit hook /home/dgk/workspace/legacy-controlplane-archive/scripts/codex_project_init_hook.py, which renders ContextForge prompt project_init_prompt and writes idempotency state under the ignored run/ directory. The hook rejects /, /home/dgk, /home/dgk/workspace, and symlink escapes after realpath, and fails open when ContextForge is unavailable.

Serena provisioning is centralized in scripts/manage_serena_project_instance.py. It derives serena-<slug>-<hash> from uid:canonical_project_root, reserves a user-local port, creates server-instances/<instance>/, installs a user systemd unit wanted by contextforge.target, registers a ContextForge gateway and project-specific virtual server, filters activate_project from that virtual server, and writes the project .codex/config.toml alias serena last.

Verification on 2026-05-29 created two disposable workspace projects concurrently. They received unique instance slugs, ports 9111 and 9112, active user units, ContextForge virtual servers with 22 tools and no exposed activate_project, project-pinned get_current_config output, and {} diagnostics for main.py through the ContextForge wrapper MCP path. Rollback removed the test units, ContextForge records, instance directories, and disposable projects. Codex project-local config remains gated by Codex project trust; untrusted new projects do not expose the local serena alias until trusted.
<!-- governance-crud:end id=dec-20260529-0047 -->

<!-- governance-crud:start id=dec-20260529-0048 -->
## dec-20260529-0048: Add live Serena verification and gateway-ordered user units

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-29
- Updated: 2026-05-29
- Tags: contextforge,serena,verification,systemd,codex

Added a safe verify command to scripts/manage_serena_project_instance.py that reconciles the current per-project Serena manifest, user unit, port, ContextForge gateway and virtual server, project-local Codex config, absence of home-level serena, and optional Codex app-server MCP tool calls. Live verification on 2026-05-29 for /home/dgk/workspace/legacy-controlplane-archive passed through serena_cf_controlplane_d46fe58a2a20_server with 22 app-server tools, no activate tool, get-current-config on the cf-controlplane project, and {} diagnostics for scripts/contextforge_mcp_wrapper.py. Updated generated user units so Serena services order after and want contextforge-gateway.service; reapplied user-unit templates without restarting, and both contextforge-gateway.service and contextforge-serena-cf-controlplane-d46fe58a2a20.service remained active. The new-project Codex trust policy remains open under oq-20260529-0001; no broad automatic trust was added.
<!-- governance-crud:end id=dec-20260529-0048 -->

<!-- governance-crud:start id=dec-20260529-0049 -->
## dec-20260529-0049: Improve empty-project Serena initialization

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-29
- Updated: 2026-05-29
- Tags: contextforge,serena,project-init,lsp,verification

Implemented empty-project Serena initialization improvements. The Serena manager now supports explicit --language on create/status/verify, create --verify --app-server, project-root-aware app-server verification, robust mcpServerStatus/list parsing for result.data/result.servers/list shapes, exposed-tool-only activate_project checks, language state reporting, manager-owned temporary LSP probe files, and safe needs_user_language_choice output for empty projects. Prompt/resource guidance was refreshed through ContextForge APIs so future agents ask for a language on empty projects and use manager commands instead of ad hoc app-server probes. Live checks passed for cf-controlplane and test-new-proj, and no automatic Codex project trust was added.
<!-- governance-crud:end id=dec-20260529-0049 -->

<!-- governance-crud:start id=dec-20260529-0050 -->
## dec-20260529-0050: Status-first empty-project Serena initialization

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-29
- Updated: 2026-05-29
- Tags: serena,project-init,codex

Empty project initialization now uses manager status preflight before provisioning. Missing .env is represented as hook default state, not a mismatch. When language is needed, status returns recommended language examples, next_action, and a one-shot create --require-workspace --language LANGUAGE --verify --app-server command. Related ancestor or descendant Serena instances are diagnostics only and never satisfy the exact canonical project root.
<!-- governance-crud:end id=dec-20260529-0050 -->

<!-- governance-crud:start id=dec-20260530-0001 -->
## dec-20260530-0001: Adopt the control-plane MVS, roadmap, and acceptance gates

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-30
- Updated: 2026-05-30
- Tags: contextforge,control-plane,mvs,acceptance,governance

Adopt the ContextForge control-plane RFC minimal viable slice, roadmap, and acceptance gates as the implementation baseline. Accepted ledger changes must flow through governance CRUD or mentality. MVS work includes project-state schema and migration, contract/capsule/policy/receipt/trace/evidence schemas, Codex conformance and trust broker behavior, semantic tool-policy checks, language-profile metadata, Serena behind a generic project-scoped adapter, a read-only project-inspector proof, service-management handoff, requirement-linked deterministic and inference-inclusive scenarios, evaluator verdicts, and reviewed governance reconciliation. Acceptance is gated by must_pass_mvs, must_pass_before_remote_or_expansion, and deferrable_with_governance_waiver classifications.
<!-- governance-crud:end id=dec-20260530-0001 -->

<!-- governance-crud:start id=dec-20260530-0002 -->
## dec-20260530-0002: Use .project/context_forge_state.json as sole project-init state authority

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-30
- Updated: 2026-05-30
- Tags: contextforge,project-state,migration,project-init

Project initialization state belongs in .project/context_forge_state.json. Legacy .env project-init keys are migration input only and must be recorded as absent, ignored, imported, conflicted, declined, deferred, or disabled according to the RFC rules. They are not a parallel authority and cannot mark a service or project verified without current evidence. Writes must be locked, schema-validated, atomic, revision-aware, root-safe, and secret-free.
<!-- governance-crud:end id=dec-20260530-0002 -->

<!-- governance-crud:start id=dec-20260530-0003 -->
## dec-20260530-0003: Require receipts, traces, and journals for mutating control-plane work

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-30
- Updated: 2026-05-30
- Tags: contextforge,consent,audit,verification,project-init

Mutating control-plane operations require typed consent receipts, adapter-independent verification traces, and step journals. apply_approved_plan consumes existing approval receipts and must not mint the approval authorizing itself. Receipts are immutable and scoped by class, plan digest, target, actor, source client, and expiry. Trace and journal records carry per-layer verification and recovery evidence.
<!-- governance-crud:end id=dec-20260530-0003 -->

<!-- governance-crud:start id=dec-20260530-0004 -->
## dec-20260530-0004: Require service-management handoff for host-wide catalog mutation

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-30
- Updated: 2026-05-30
- Tags: contextforge,catalog,service-management,control-plane

Normal project initialization and the general control-plane MCP surface must not perform raw host-wide catalog CRUD or candidate promotion. When catalog promotion, catalog repair, duplicate resolution, or candidate canonicalization is required, project init emits a service-management handoff and stops. The dedicated service-management workflow must inspect, deduplicate, classify scope and transport, plan through stock ContextForge APIs and documented scripts, and require explicit approval before mutation.
<!-- governance-crud:end id=dec-20260530-0004 -->

<!-- governance-crud:start id=dec-20260530-0005 -->
## dec-20260530-0005: Keep service memory reference-only for governance in v1

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-30
- Updated: 2026-05-30
- Tags: contextforge,governance,memory,serena,service-memory

Governance ledgers remain authoritative for decisions, open questions, parked intentions, consent, and project policy. Serena is one instance of a generic service_memory_provider, not a special governance authority. Service-local memory may store working notes, recall hints, code-navigation context, governance references, and governance proposals, but v1 does not use generated governance projections or bidirectional sync. If service memory conflicts with a governance ledger, flag the conflict and continue using the ledger as authority.
<!-- governance-crud:end id=dec-20260530-0005 -->

<!-- governance-crud:start id=dec-20260530-0006 -->
## dec-20260530-0006: Gate local auth, token material, trust, and remote exposure separately

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-30
- Updated: 2026-05-30
- Tags: contextforge,auth,tokens,trust,remote-exposure

The v1 local profile uses loopback authenticated HTTP with wrapper fallback where needed, but local assistant tokens must be non-admin and least-privilege. User-global trust, user-global config writes, token material changes, secret value writes, and remote exposure require separate human approval and evidence. Remote exposure is non-default, opt-in, scoped, separately tokenized, and must deny control-plane mutation, catalog/admin, trust, token, and secret-value workflows unless a later approved RFC changes the model.
<!-- governance-crud:end id=dec-20260530-0006 -->

<!-- governance-crud:start id=dec-20260531-0001 -->
## dec-20260531-0001: Use stable service identity IDs for project-init service state

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-31
- Updated: 2026-05-31
- Tags: contextforge,project-init,idempotency,service-identity,cleanup

Project-init service selection, approval, application, readback, validation, cleanup, and state reconciliation must identify services by stable ContextForge service identity IDs rather than descriptive service names, client labels, virtual server names, tool prefixes, or binding strings alone. serviceBinding, serviceFamily, virtualServer, piToolPrefix, descriptors, and display names are routing or presentation metadata only. During reconciliation, any persisted service ID that is absent from the current ContextForge catalog must be removed from .project/context_forge_state.json regardless of label matches or older descriptor artifacts. Stale, mismatched, or no-longer-existing service IDs cannot satisfy selection, idempotency, or validation. Project-state writes remain locked, schema-validated, atomic, revision-aware, root-safe, and secret-free.
<!-- governance-crud:end id=dec-20260531-0001 -->

<!-- governance-crud:start id=dec-20260531-0002 -->
## dec-20260531-0002: Keep project-init validation evaluator-led and target-client-visible

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-31
- Updated: 2026-05-31
- Tags: contextforge,project-init,inference-testing,validation,evaluator

Project-init validation must prove the target client can see and call the expected ContextForge route. Built-in tools, direct shell commands, direct SSH or tmux checks, backend-only reachability, helper scripts, and Python module invocations are not valid substitutes for Pi-visible or Codex-visible ContextForge tool routes. If a skipped-service follow-up cannot exercise the imported ContextForge route, the assistant must say so and must not record the substitute as ContextForge proof. Inference-inclusive validation remains evaluator-led: do not add deterministic transcript keyword guards, semantic verdict overrides, or hard-coded failure signatures. The only deterministic evaluation step may parse the structured evaluator result and fail or pass from the evaluator verdict. Evaluator prompts must catch tool-not-found false completion, role confusion, proxy validation, skipped-service proof substitution, missing cleanup, and stale service-ID handling.
<!-- governance-crud:end id=dec-20260531-0002 -->

<!-- governance-crud:start id=dec-20260531-0003 -->
## dec-20260531-0003: Number project-init choices and make reload instructions explicit

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-05-31
- Updated: 2026-05-31
- Tags: contextforge,project-init,ux,reload,options

Every project-init prompt that presents user options must number the options and accept selection numbers as well as option IDs. Where the client supports a selectable form, prefer the form over free-text-only option lists. Reload or restart-required copy must give explicit next responses, for example: after restarting, respond validate to run validation or skip validation to record presumed working without verification. Do not leave the user with vague phrasing such as choose whether to validate, and do not require users to answer with only descriptive service names.
<!-- governance-crud:end id=dec-20260531-0003 -->

<!-- governance-crud:start id=dec-20260616-0001 -->
## dec-20260616-0001: Use ContextForge naming for the project

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/legacy-controlplane-archive
- Created: 2026-06-16
- Updated: 2026-06-16
- Tags: contextforge,naming,documentation,governance

Use ContextForge, Context Forge, or contextforge as the project name in human-facing documentation and coordination artifacts. Treat `cf-controlplane` as the canonical workspace slug and filesystem path for this repository. Retired predecessor workspace names are legacy identifiers only where exact historical evidence, service names, project hashes, registry ids, or compatibility surfaces require a neutral reference. Do not rename live services, project-state identities, Serena slugs, GitHub repository names, or filesystem paths as part of ordinary cleanup; any such migration requires a separate explicit plan, approval, rollback story, and runtime readback evidence.
<!-- governance-crud:end id=dec-20260616-0001 -->

<!-- governance-crud:start id=dec-20260616-0002 -->
## dec-20260616-0002: Treat agent operating surface as project-critical state

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/cf-controlplane
- Created: 2026-06-16
- Updated: 2026-06-17
- Tags: agent-operations,roadmap,skills,hooks,worktrees,continuity

The active Codex operating surface is project-critical state, not incidental
tooling. For ContextForge roadmap work, stale worktrees, missing repo-local
skills, path-scoped hook trust drift, outdated roadmap copies, and
cross-worktree skill reads can degrade the operating agent's judgment and
continuity as directly as code or service drift degrades the product.

Every substantial conductor loop must include an agent operating integrity
check before implementation or completion claims: active working directory,
branch, roadmap source path, repo-local skill availability in the active tree,
hook activation/trust scope, active subagents and delegation contracts, formal
goal state, and whether any required instruction or artifact was read from a
different worktree. If the active tree is stale or missing required operating
assets, that is first-class project debt and must be reconciled, tracked, or
explicitly deferred; it must not be treated as a harmless local inconvenience.

Formal Codex goal state is part of the operating surface. The user is the
ultimate authority over goal intent and over whether a dynamic-loop goal has
completed for purposes of refinement. The user has persistently authorized and
instructed this self-referential goal-maintenance method across goal
iterations, not merely on request-by-request occasions. This persistent
directive must signal itself forward inside every successor formal goal: when
the current goal text shows this directive, the agent is authorized and
instructed to preserve it, recognize future user refinements as authoritative,
retire stale dynamic-loop formal goals as complete when replacement is the
goal-maintenance act, and immediately instantiate the refined formal goal
without stale-goal lock-in.

This authorized/instructed interrupt protocol is exempt from simplistic
completion rules that do not grasp the self-referential method, because the
dynamic-loop goal's purpose includes maintaining, refining, and replacing the
goal loop itself. The conductor must still use the formal goal tool truthfully:
do not mark ordinary roadmap work complete merely because it is inconvenient or
partial. The special completion transition applies to persistent or immediate
user-directed goal-loop refinement/replacement, not to unfinished roadmap
slices. After replacement, the new formal goal must carry this interrupt
protocol forward; the roadmap, governance ledgers, and GitHub issues remain
the durable surrogate ledger for subgoals, evidence, operating-surface debt,
and cross-compaction continuity.

The dirty holding checkout retirement is tracked by GitHub issue #15.
Clean-worktree test hermeticity is tracked by issue #14. This decision does
not authorize destructive cleanup, reset, rebase, global hook installation, or
copying secrets into Git; preservation and approval boundaries still apply.
<!-- governance-crud:end id=dec-20260616-0002 -->

<!-- governance-crud:start id=dec-20260617-0001 -->
## dec-20260617-0001: Allow scoped dependency installation for control-plane work

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/cf-controlplane
- Created: 2026-06-17
- Updated: 2026-06-17
- Tags: dependencies,venv,tooling,operator-approval

The user explicitly approved the operating agent to install software and Python/venv libraries needed to support scoped ContextForge control-plane development and validation work in /home/dgk/workspace/cf-controlplane. Use the project Python policy by default: create or repair the ignored local .venv with uv venv .venv when needed, install Python dependencies with uv pip install --python .venv/bin/python ..., and keep installed environments, caches, secrets, OAuth state, runtime evidence, service state, and generated local artifacts out of Git unless separately promoted as sanitized source. This approval does not authorize global Codex config mutation, hook trust/state mutation, runtime secret/OAuth/trust copy, service/process/systemd/registry/Pi global config mutation, destructive git operations, mutation of /home/dgk/workspace/legacy-controlplane-archive, or helper/project-init apply steps that require challenge approval.
<!-- governance-crud:end id=dec-20260617-0001 -->

<!-- governance-crud:start id=dec-20260617-0002 -->
## dec-20260617-0002: Separate live, development, and client Docker ContextForge surfaces

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/cf-controlplane
- Created: 2026-06-17
- Updated: 2026-06-17
- Tags: contextforge,surface-boundaries,docker,clients,operations

ContextForge work must distinguish three surfaces. The legacy/live ContextForge surface is the currently active user/operator environment and is strictly read-only: no registry writes, service registration, prompt/resource upserts, token/team/admin changes, env edits, process restarts, service stops/starts, database writes, config rewrites, hook/trust changes, port changes, or cleanup actions. It may be used only for non-mutating evidence such as health/readiness checks, config/path inspection, process/socket inspection, logs, diagnostics, and comparison. The ContextForge development Docker surface is the isolated mutable gateway/app surface for cf-controlplane validation, with separate ports, volumes, env, registry state, credentials, and test data. Registration tests, endpoint validation, resettable integration work, and other mutable experiments belong there. Client Docker test surfaces are separate Dockerized client foils against the development Docker surface; for now they are Pi and OpenCode only and use the already served local Qwen/llama.cpp path as configuration, not installation. Evidence and claims must name the exercised surface: legacy/live read-only, ContextForge dev Docker, Pi client Docker, or OpenCode client Docker.
<!-- governance-crud:end id=dec-20260617-0002 -->

<!-- governance-crud:start id=dec-20260617-0003 -->
## dec-20260617-0003: Use Pi and OpenCode client Docker surfaces with local Qwen

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/cf-controlplane
- Created: 2026-06-17
- Updated: 2026-06-17
- Tags: clients,docker,opencode,pi,llama-cpp,qwen

For the indefinite cf-controlplane development path, use only the Pi and OpenCode client Docker surfaces unless the user explicitly reopens another client. Both clients should use the existing local llama.cpp-hosted Qwen 3.6 A3B model as configuration/default model state, not as an installation task. Avoid Codex and Gemini client containers for this development project because Pi and OpenCode are the preferred real client foils.
<!-- governance-crud:end id=dec-20260617-0003 -->

<!-- governance-crud:start id=dec-20260617-0004 -->
## dec-20260617-0004: Retire cf-controlplane naming through GitHub-tracked slices

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/cf-controlplane
- Created: 2026-06-17
- Updated: 2026-06-17
- Tags: naming,cf-controlplane,github,compatibility,migration

Retired predecessor workspace naming is legacy naming. In cf-controlplane work, treat references to predecessor workspace names as historical or compatibility identifiers only until they can be eliminated safely. As agents encounter active predecessor naming, they should use GitHub issues or PR-linked issue comments to track and gradually retire it in focused, reviewable slices. Do not perform broad opportunistic renames that could break service identities, registry records, Serena tool names, project-state compatibility, or historical evidence; classify each occurrence as active, compatibility, or historical before changing it.
<!-- governance-crud:end id=dec-20260617-0004 -->

<!-- governance-crud:start id=dec-20260617-0005 -->
## dec-20260617-0005: Use stock bridge and Pi shim first for dev Docker validation

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/cf-controlplane
- Created: 2026-06-17
- Updated: 2026-06-17
- Tags: docker,pi,transceiver,contextforge,validation

For issue #41, the first mutable integration path is the isolated ContextForge development Docker surface, not the legacy/live host ContextForge surface. Start with the stock ContextForge bridge/transceiver path (`python -m mcpgateway.translate`) and the low-risk repo-local `mentality` stdio MCP backend, exposed by the `mentality-transceiver` compose service on reserved port 9201. Register it only into the development gateway as `mentality-dev-docker` / `mentality_dev_docker_server` and validate direct `/mcp` plus virtual ContextForge `/mcp` behavior before adding custom wrapper logic.

For Pi client validation, use the existing TypeScript global shim path under `pi-extensions/contextforge-global-shim` as the first validation route because Pi is not a native MCP client and the shim already maps ContextForge virtual-server tools into Pi-native extension tools. A direct ContextForge API adapter remains an option only if it proves simpler and does not introduce new token, secret, or global Pi mutation boundaries. Pi global install/upgrade and `/reload` remain explicit human approval boundaries.
<!-- governance-crud:end id=dec-20260617-0005 -->

<!-- governance-crud:start id=dec-20260619-0001 -->
## dec-20260619-0001: Keep deterministic reset separate from semantic validation

- Ledger: decisions
- Status: accepted
- Repository: /home/dgk/workspace/cf-controlplane
- Created: 2026-06-19
- Updated: 2026-06-19
- Tags: validation,idempotency,agents,testing,architecture

Deterministic state setup and semantic agent validation are separate responsibilities. Evidence preservation, target-client reset, workspace fixture creation, fixed postcondition checks, and verifier invocation must be implemented as idempotent commands or scripts with stable, repeatable outcomes. Agents and humans must not be asked to infer residue deltas or decide whether cleanup is clean enough; that creates a second non-deterministic validation problem. Reserve high-dimensional language-model judgment for the semantic work: conducting the code-assistant dialogue, observing real assistant/tool behavior, evaluating protocol adherence against the full use-case story, and writing the interaction narrative from evidence. Validation gates must not invert these responsibilities by using brittle pattern matching for semantic dialogue success while relying on non-deterministic model judgment for simple state reset.
<!-- governance-crud:end id=dec-20260619-0001 -->
